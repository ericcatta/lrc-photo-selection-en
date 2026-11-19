"""Local OpenAI configuration. No network calls or billing operations here."""
import base64
import ctypes
import json
import os
import sys
from pathlib import Path

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class MacKeychain:
    """Generic-password entry accessed in process; secrets never enter argv/files."""
    service = b'lrc-photo-selection-en-openai'
    account = b'api-key'

    def __init__(self):
        if sys.platform != 'darwin':
            raise RuntimeError('macOS Keychain unavailable')
        self.lib = ctypes.CDLL('/System/Library/Frameworks/Security.framework/Security')
        self.cf = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        ptr = ctypes.c_void_p
        u32 = ctypes.c_uint32
        self.lib.SecKeychainFindGenericPassword.argtypes = [ptr, u32, ctypes.c_char_p, u32, ctypes.c_char_p, ctypes.POINTER(u32), ctypes.POINTER(ptr), ctypes.POINTER(ptr)]
        self.lib.SecKeychainFindGenericPassword.restype = ctypes.c_int32
        self.lib.SecKeychainAddGenericPassword.argtypes = [ptr, u32, ctypes.c_char_p, u32, ctypes.c_char_p, u32, ptr, ctypes.POINTER(ptr)]
        self.lib.SecKeychainAddGenericPassword.restype = ctypes.c_int32
        self.lib.SecKeychainItemModifyAttributesAndData.argtypes = [ptr, ptr, u32, ptr]
        self.lib.SecKeychainItemModifyAttributesAndData.restype = ctypes.c_int32
        self.lib.SecKeychainItemFreeContent.argtypes = [ptr, ptr]
        self.cf.CFRelease.argtypes = [ptr]

    def _find(self):
        length, data, item = ctypes.c_uint32(), ctypes.c_void_p(), ctypes.c_void_p()
        status = self.lib.SecKeychainFindGenericPassword(None, len(self.service), self.service, len(self.account), self.account, ctypes.byref(length), ctypes.byref(data), ctypes.byref(item))
        if status == -25300:  # errSecItemNotFound
            return None, None
        if status:
            raise RuntimeError('Keychain access failed')
        try:
            try:
                value = ctypes.string_at(data, length.value).decode('utf-8')
            except UnicodeDecodeError:
                if item:
                    self.cf.CFRelease(item)
                raise RuntimeError('Invalid key in Keychain') from None
        finally:
            self.lib.SecKeychainItemFreeContent(None, data)
        return value, item

    def get(self):
        value, item = self._find()
        if item:
            self.cf.CFRelease(item)
        return value

    def set(self, value):
        _, item = self._find()
        encoded = value.encode('utf-8')
        try:
            if item:
                status = self.lib.SecKeychainItemModifyAttributesAndData(item, None, len(encoded), ctypes.c_char_p(encoded))
            else:
                status = self.lib.SecKeychainAddGenericPassword(None, len(self.service), self.service, len(self.account), self.account, len(encoded), ctypes.c_char_p(encoded), None)
            if status:
                raise RuntimeError('Keychain save failed')
        finally:
            if item:
                self.cf.CFRelease(item)


class OpenAIConfigInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    model: str = Field(default='', max_length=200, pattern=r'^[A-Za-z0-9._:-]*$')
    api_key: SecretStr | None = None


class OpenAIConfig:
    def __init__(self, root: Path, keychain=None):
        self.path = root / 'openai-config.json'
        self.keychain = keychain

    def secrets(self):
        if self.keychain is None:
            self.keychain = MacKeychain()
        return self.keychain

    def read(self):
        model = json.loads(self.path.read_text()).get('model', '') if self.path.exists() else ''
        try:
            has_key = bool(self.secrets().get())
            error = None
        except RuntimeError:
            has_key, error = False, 'Keychain unavailable: no key verified.'
        return {'configured': has_key and bool(model), 'key_configured': has_key, 'model': model,
                'storage': 'macOS Keychain', 'analysis_enabled': True, 'error': error}

    def save(self, body):
        if body.api_key is not None:
            key = body.api_key.get_secret_value()
            if not key or key != key.strip() or len(key) > 4096:
                raise HTTPException(422, 'Invalid API key.')
            try:
                self.secrets().set(key)
                # Availability belongs to the credential/account last checked.
                (self.path.parent / 'openai-available-models.json').unlink(missing_ok=True)
            except RuntimeError:
                raise HTTPException(503, 'Unable to save the key in Keychain.') from None
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_suffix('.pending')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump({'schema_version': 1, 'model': body.model}, stream)
        temporary.replace(self.path)
        return self.read()


def register_openai_config(app, root, *, keychain=None):
    config = OpenAIConfig(root, keychain)
    app.state.openai_config = config

    @app.get('/api/openai/config')
    def get_config():
        return config.read()

    @app.put('/api/openai/config')
    async def put_config(request: Request):
        # Default validation responses include raw invalid inputs: sanitize here so
        # malformed key fields cannot be echoed by FastAPI's validation handler.
        try:
            body = OpenAIConfigInput.model_validate(await request.json())
        except (ValueError, TypeError):
            raise HTTPException(422, 'Invalid OpenAI configuration.') from None
        return config.save(body)


def build_responses_request(model: str, instructions: str, previews: list[bytes], *, context: str = '', max_output_tokens: int = 1000):
    """Prepare only; caller controls authorization, budget, transport and usage.

    Original instructions are a standalone content item, preserved exactly.
    Only caller-supplied JPEG/PNG derived preview bytes are accepted, never paths.
    """
    if not model or not isinstance(instructions, str) or not 1 <= max_output_tokens <= 16000:
        raise ValueError('Invalid request')
    if not previews or len(previews) > 100:
        raise ValueError('Invalid preview count')
    content = [{'type': 'input_text', 'text': instructions}]
    for data in previews:
        if not isinstance(data, bytes) or not data or len(data) > 24 * 1024 * 1024:
            raise ValueError('Invalid preview')
        if data.startswith(b'\xff\xd8\xff'):
            mime = 'image/jpeg'
        elif data.startswith(b'\x89PNG\r\n\x1a\n'):
            mime = 'image/png'
        else:
            raise ValueError('JPEG or PNG previews only')
        content.append({'type': 'input_image', 'image_url': 'data:'+mime+';base64,'+base64.b64encode(data).decode('ascii'), 'detail': 'auto'})
    return {'model': model, 'store': False, 'max_output_tokens': max_output_tokens,
            'input': [{'role': 'developer', 'content': [{'type': 'input_text', 'text': 'Assess only previews for photo selection. Report uncertainty and unverifiable criteria. Do not modify images. Respond in English.\n'+context}]},
                      {'role': 'user', 'content': content}]}
