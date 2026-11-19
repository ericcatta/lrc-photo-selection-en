"""Exercise the actual Common module with synthetic SDK storage; no Lightroom access."""
from pathlib import Path

import pytest
from lupa.lua51 import LuaRuntime

PLUGIN = Path(__file__).resolve().parents[2] / 'plugin/lrc-photo-selection.lrplugin'


def storage():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(r'''
        state = {files={}, step=0}
        os.rename = nil
        local function operation()
            state.step = state.step + 1
            return state.step ~= state.failAt
        end
        local function confined(path)
            assert(path:match('^/synthetic/appData/lrc%-photo%-selection%-plugin%-en/'))
        end
        local file = {}
        function file.exists(path) confined(path); return state.files[path] and 'file' end
        function file.createAllDirectories(path) confined(path); return true end
        function file.readFile(path) confined(path); return state.files[path] end
        function file.delete(path)
            confined(path)
            if not operation() then return false end
            state.files[path] = nil
            return true
        end
        function file.move(source, target)
            confined(source); confined(target)
            if not operation() then return false end
            assert(not state.files[target], 'SDK move cannot overwrite')
            assert(state.files[source])
            state.files[target], state.files[source] = state.files[source], nil
            return true
        end
        io.open = function(path, mode)
            confined(path); assert(mode == 'wb')
            if not operation() then return nil end
            state.files[path] = ''
            return {
                write=function(_, value)
                    if not operation() then return nil end
                    state.files[path] = value; return true
                end,
                flush=function() return operation() end,
                close=function() return operation() end,
            }
        end
        local sdk = {LrFileUtils=file, LrPathUtils={
            child=function(a,b) return a .. '/' .. b end,
            getStandardFilePath=function(kind) assert(kind=='appData'); return '/synthetic/appData' end,
        }}
        function import(name) return sdk[name] or {} end
    ''')
    lua.globals().package.loaded.JSON = lua.execute((PLUGIN / 'JSON.lua').read_text())
    lua.globals().common = lua.execute((PLUGIN / 'Common.lua').read_text())
    lua.execute("path = common.file('rating-cat', 'photo:1')")
    return lua


def test_legacy_read_and_repeated_sdk_writes_without_os_rename():
    lua = storage()
    lua.execute('''
        assert(common.read(path) == nil)
        state.files[path] = '{"batch_id":"legacy"}'
        assert(common.read(path).batch_id == 'legacy')
        common.write(path, {batch_id='first'})
        common.write(path, {batch_id='second'})
        assert(common.read(path).batch_id == 'second')
    ''')


@pytest.mark.parametrize('fail_at', range(1, 8))
def test_failed_replacement_keeps_committed_rating_marker(fail_at):
    lua = storage()
    lua.globals().fail_at = fail_at
    lua.execute('''
        common.write(path, {batch_id='old'})
        common.write(path, {batch_id='old'}) -- exercise deletion of older backup too
        state.step, state.failAt = 0, fail_at
        local ok = pcall(common.write, path, {batch_id='new'})
        assert(not ok)
        assert(common.read(path).batch_id == 'old')
        state.failAt = nil
        common.write(path, {batch_id='recovered'})
        assert(common.read(path).batch_id == 'recovered')
    ''')


@pytest.mark.parametrize('fail_at', range(1, 6))
def test_failed_first_write_never_silently_reads_partial_state(fail_at):
    lua = storage()
    lua.globals().fail_at = fail_at
    lua.execute('''
        state.failAt = fail_at
        assert(not pcall(common.write, path, {batch_id='new'}))
        local ok, value = pcall(common.read, path)
        if fail_at == 1 then assert(ok and value == nil) else assert(not ok) end
    ''')


def test_interrupted_move_and_invalid_state_fail_closed():
    lua = storage()
    lua.execute('''
        state.files[path .. '.previous'] = '{"batch_id":"old"}'
        state.files[path .. '.pending'] = '{"batch_id":"new"}'
        assert(common.read(path).batch_id == 'old')
        common.write(path, {batch_id='recovered'})
        assert(common.read(path).batch_id == 'recovered')
        state.files[path] = 'null'
        assert(not pcall(common.read, path))
        state.files[path] = '{bad'
        assert(not pcall(common.read, path))
    ''')


def test_external_paths_rejected_before_io_and_legacy_pending_is_not_absent():
    lua = storage()
    lua.execute('''
        assert(not pcall(common.write, '/photos/original.jpg', {}))
        assert(not pcall(common.read, '/catalog.lrcat'))
        assert(not pcall(common.file, '../photos', 'x'))
        state.files[path .. '.tmp'] = '{"batch_id":"legacy-interrupted"}'
        assert(not pcall(common.read, path))
        assert(not pcall(common.write, path, {}))
        assert(state.step == 0)
    ''')
