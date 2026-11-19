"""Offline guide and generated content checks; never opens Lightroom."""
import json
from pathlib import Path
import subprocess
import sys

from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / 'plugin/lrc-photo-selection.lrplugin'


def test_guide_generated_content_is_current_and_shared():
    subprocess.run([sys.executable, str(ROOT / 'scripts/generate_workflow_guide.py'), '--check'], check=True)
    canonical = json.loads((ROOT / 'docs/workflow-guide.json').read_text())
    assert json.loads((ROOT / 'web/src/guide-data.json').read_text()) == canonical
    lua = LuaRuntime(unpack_returned_tuples=True)
    data = lua.execute((PLUGIN / 'GuideData.lua').read_text())
    assert data.schema_version == 1 and len(data.steps) == 7
    for index, step in enumerate(canonical['steps'], 1):
        assert data.steps[index].title == step['title']
        assert data.steps[index].body == step['body']
    info = lua.execute((PLUGIN / 'Info.lua').read_text())
    assert any(item.file == 'GuideMenu.lua' for item in info.LrLibraryMenuItems.values())
    guide_text = json.dumps(canonical, ensure_ascii=False)
    for item in info.LrLibraryMenuItems.values():
        if item.file != 'GuideMenu.lua':
            assert item.title in guide_text, f'Guide must name actual menu command: {item.title}'


def test_guide_runs_offline_with_only_sdk_view_and_context():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().package.loaded.GuideData = lua.execute((PLUGIN / 'GuideData.lua').read_text())
    lua.execute('''
      test = {}
      local view = {}
      for _, name in ipairs({'column','static_text','scrolled_view','push_button'}) do
        view[name] = function(_, value) return value end
      end
      function import(name)
        if name == 'LrView' then return {osFactory=function() return view end} end
        if name == 'LrDialogs' then return {presentModalDialog=function(dialog)
          test.dialog=dialog; return 'ok'
        end} end
        if name == 'LrFunctionContext' then return {postAsyncTaskWithContext=function(_, fn) fn() end} end
        error('Guide attempted unavailable SDK dependency: '..name)
      end
    ''')
    lua.globals().package.loaded.Guide = lua.execute((PLUGIN / 'Guide.lua').read_text())
    lua.execute((PLUGIN / 'GuideMenu.lua').read_text())
    assert lua.globals().test.dialog.title == 'From Lightroom to selection and back'
    assert lua.globals().test.dialog.actionVerb == 'Close guide'
    assert lua.globals().test.dialog.contents[1][1].title


def test_english_plugin_uses_isolated_identity_storage_and_connection():
    lua = LuaRuntime(unpack_returned_tuples=True)
    info = lua.execute((PLUGIN / 'Info.lua').read_text())
    assert info.LrToolkitIdentifier == 'com.ericcatta.lrc-photo-selection-en'
    assert info.LrPluginName == 'Photo Selection (English)'
    common = (PLUGIN / 'Common.lua').read_text()
    assert "'lrc-photo-selection-plugin-en'" in common
    assert "'loopback-token-en'" in common
    assert "'http://127.0.0.1:8766'" in common
    configure = (PLUGIN / 'Configure.lua').read_text()
    assert "'LrC Photo Selection EN'" in configure
    assert "'LrC Photo Selection'" not in configure
