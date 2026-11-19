"""Lua SDK simulation: no Lightroom process or catalog is accessed."""
from pathlib import Path
import pytest
from lupa.lua51 import LuaRuntime

PLUGIN = Path(__file__).resolve().parents[2] / 'plugin/lrc-photo-selection.lrplugin'


def test_lua51_syntax_and_json_timestamp_precision():
    runtime = LuaRuntime(unpack_returned_tuples=True)
    compile_lua = runtime.eval('function(s) return assert(loadstring(s)) end')
    for path in PLUGIN.glob('*.lua'):
        compile_lua(path.read_text())
    codec = runtime.execute((PLUGIN / 'JSON.lua').read_text())
    value = 798123456.1234567
    assert codec.decode(codec.encode(value)) == value
    assert codec.decode(codec.encode('Wedding — café')) == 'Wedding — café'


def simulate(current=0, edited=100, xmp=True, target=1, previous=False, fail_journal=False, cancel=False, claim=True, cancel_inside_gate=False, receipt_during_gate=False):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().options = lua.table_from({'current': current, 'edited': edited, 'xmp': xmp, 'target': target,
                                          'previous': previous, 'failJournal': fail_journal, 'cancel': cancel, 'claim': claim,
                                          'cancelInsideGate': cancel_inside_gate, 'receiptDuringGate': receipt_during_gate})
    lua.execute(r'''
      test = { writes=0, claimed=false, files={}, events={} }
      local props
      local photo = {localIdentifier=1}
      function photo:getRawMetadata(key)
        if key == 'uuid' then return 'photo-uuid' end
        if key == 'rating' then return options.current end
        if key == 'lastEditTime' then return options.edited end
        error('Unexpected metadata read: ' .. key)
      end
      function photo:setRawMetadata(key, value)
        assert(key == 'rating' and value == 1, 'Only one-star mutation allowed')
        assert(test.files['rating-cat/photo-uuid:1'], 'Journal must precede write')
        assert(test.claimed, 'Backend claim must precede write')
        test.writes = test.writes + 1
        options.current = value
        table.insert(test.events, 'rating')
      end
      local catalog = {}
      function catalog:findPhotoByUuid(uuid) return photo end
      function catalog:getAllPhotos() return {photo} end
      function catalog:withWriteAccessDo(name, fn, params)
        if options.cancelInsideGate then options.cancel = true end
        if options.receiptDuringGate then
          test.files['rating-cat/photo-uuid:1'] = {batch_id='batch'}
          test.files['batch-batch/photo-uuid:1'] = {photo_id='photo-uuid:1',status='applied',before=0,after=1}
          options.current = 1
        end
        fn(); return 'executed'
      end
      local item = {photo_id='photo-uuid:1', uuid='photo-uuid', local_id=1,
                    expected_rating=0, expected_edit_time=100, target_rating=options.target}
      local service = {id='service', title='SYNTHETIC', catalog_id='cat', revision=1, status='ready',
        photos={{id='photo-uuid:1',uuid='photo-uuid',local_id=1,baseline_rating=0,baseline_edit_time=100}}}
      local plan = {schema_version=1, batch_id='batch',service_id='service',catalog_id='cat',revision=1,items={item}}
      if options.previous then test.files['rating-cat/photo-uuid:1'] = {batch_id='old-batch'} end
      local common = {}
      function common.run(_, fn) local ok, err=pcall(fn, {}); if not ok then test.error=tostring(err) end end
      function common.catalog() return catalog, '/synthetic/catalog.lrcat', 'Synthetic catalog' end
      function common.registration() return 'cat' end
      function common.key(value) return value end
      function common.assertCatalog() end
      function common.file(kind,key) return kind .. '/' .. key end
      function common.read(path) return test.files[path] end
      function common.write(path,value)
        if options.failJournal and path:match('^rating') then error('Synthetic disk failure') end
        test.files[path]=value
        table.insert(test.events, 'journal')
      end
      function common.request(method,path,data)
        if path == '/api/services' then return {service} end
        if path == '/api/services/service' then return service end
        if path:match('/rating%-plan/latest$') then return plan end
        if path:match('/rating%-plan/claim$') then
          if not options.claim then error('Synthetic stale plan') end
          test.claimed=true; return {ok=true}
        end
        if path:match('/rating%-receipts$') then test.receipt=data; return {ok=true} end
        error('Unexpected request ' .. path)
      end
      package.loaded.Common = common
      package.loaded.Guide = {button=function() return {} end}
      local view = {}
      for _, name in ipairs({'column','static_text','popup_menu','checkbox','edit_field','scrolled_view'}) do view[name]=function(_,v) return v end end
      local sdk = {
        LrBinding={makePropertyTable=function() props={}; return props end},
        LrView={osFactory=function() return view end, bind=function(value) return value end},
        LrDialogs={
          presentModalDialog=function(dialog)
            if dialog.title == 'Confirm star application' then
              props.xmpChecked=options.xmp
              test.operations = props.operations
              test.xmpBinding = dialog.actionBinding.enabled.key
            end
            return 'ok'
          end,
          message=function(title, message) test.messageTitle=title; test.message=message end,
        },
        LrProgressScope=function()
          return {isCanceled=function() return options.cancel end, setPortionComplete=function() end, done=function() end}
        end,
      }
      function import(name) return assert(sdk[name], name) end
    ''')
    lua.globals().package.loaded.Selection = lua.execute((PLUGIN / 'Selection.lua').read_text())
    lua.execute((PLUGIN / 'Apply.lua').read_text())
    return lua.globals().test


def test_only_zero_to_one_after_claim_and_journal():
    result = simulate()
    assert result.error is None
    assert result.writes == 1
    assert result.receipt.results[1].status == 'applied'
    assert result.receipt.results[1].before == 0
    assert result.receipt.results[1].after == 1


@pytest.mark.parametrize('rating', [1, 3, 5])
def test_existing_stars_are_not_overwritten(rating):
    result = simulate(current=rating)
    assert result.writes == 0
    assert result.receipt.results[1].status == 'conflict'


def test_manual_edit_after_import_is_preserved():
    result = simulate(edited=101)
    assert result.writes == 0
    assert result.receipt.results[1].status == 'conflict'


@pytest.mark.parametrize('options', [{'target': 5}, {'claim': False}, {'fail_journal': True}])
def test_unsafe_or_unverified_conditions_never_write(options):
    result = simulate(**options)
    assert result.writes == 0
    assert result.error is not None


def test_previous_attempt_and_user_cancellation_never_write():
    for options in [{'previous': True}, {'cancel': True}]:
        result = simulate(**options)
        assert result.writes == 0
        assert result.receipt.results[1].status == 'skipped'


def test_cancel_while_waiting_for_catalog_write_gate():
    result = simulate(cancel_inside_gate=True)
    assert result.writes == 0
    assert result.receipt.results[1].status == 'skipped'
    assert result.files['rating-cat/photo-uuid:1'] is None


def test_concurrent_completed_outcome_is_reused():
    result = simulate(receipt_during_gate=True)
    assert result.writes == 0
    assert result.receipt.results[1].status == 'applied'
    assert result.files['batch-batch/photo-uuid:1'].status == 'applied'


def test_confirmation_lists_exact_operations():
    result = simulate()
    assert '[photo-uuid:1] · 0 → 1' in result.operations


def test_append_uploads_only_new_preview_and_show_selects_exact_candidate():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(r'''
    test = {}
    local function newPhoto(i)
        local photo = {localIdentifier=i}
        function photo:getRawMetadata(key)
            if key == 'uuid' then return 'u' .. i end
            if key == 'lastEditTime' then return 40 end
        end
        function photo:requestJpegThumbnail(_, _, callback)
            assert(i == 2, 'Only the new photo needs a preview')
            callback('jpeg')
        end
        return photo
    end
    local oldPhoto, newPhoto = newPhoto(1), newPhoto(2)
    local targets = {oldPhoto, newPhoto}
    local catalog = {}
    function catalog:getTargetPhoto() return targets[1] end
    function catalog:getTargetPhotos() return targets end
    function catalog:batchGetRawMetadata(photos)
        local out = {}
        for _, photo in ipairs(photos) do
            out[photo] = {uuid=photo:getRawMetadata('uuid'), rating=0, lastEditTime=40}
        end
        return out
    end
    function catalog:batchGetFormattedMetadata(photos)
        local out = {}
        for _, photo in ipairs(photos) do out[photo] = {fileName='duplicate.jpg'} end
        return out
    end
    function catalog:findPhotoByUuid(uuid) return uuid == 'u1' and oldPhoto or newPhoto end
    function catalog:setSelectedPhotos(active, others)
        assert(active == newPhoto and #others == 0)
        targets = {active}
        test.selected = true
    end
    local view = {}
    for _, name in ipairs({'column','static_text','popup_menu','edit_field'}) do
        view[name] = function(_, props) return props end
    end
    local sdk = {
        LrBinding={makePropertyTable=function() return {} end},
        LrView={osFactory=function() return view end, bind=function(value) return value end},
        LrDialogs={presentModalDialog=function() return 'ok' end,
            confirm=function() return 'other' end, message=function() error('Unexpected dialog') end},
        LrDate={}, LrTasks={},
        LrProgressScope=function()
            return {isCanceled=function() return false end, setPortionComplete=function() end, done=function() end}
        end,
    }
    function import(name) return assert(sdk[name], name) end
    local service = {id='s',title='SYNTHETIC',catalog_id='cat',status='ready',
        photos={{id='u1:1',uuid='u1',local_id=1,preview_ready=true},{id='u2:2',uuid='u2',local_id=2}},
        selected_ids={'u2:2'}}
    local common = {}
    function common.run(_, fn) fn({}) end
    function common.token() return 'token' end
    function common.catalog() return catalog, '/synthetic/catalog.lrcat', 'Synthetic catalog' end
    function common.registration() return 'cat' end
    function common.file(_, key) return key end
    function common.read(_) return nil end
    function common.assertCatalog(_) end
    function common.key(value) return value end
    function common.newID(_) return 'append-uuid' end
    function common.write(_, value)
        if value.manifest then assert(value.append_to == 's' and value.manifest.id == 'append-uuid') end
    end
    function common.openBrowser() test.opened = true end
    function common.request(method, path, data, media)
        if path == '/api/services' then return {service} end
        if path == '/api/services/s' then return service end
        if path == '/api/services/s/append' then
            assert(data.id == 'append-uuid' and #data.photos == 2 and data.catalog_id == 'cat')
            service.status = 'importing'
            return {completed=false, photo_ids={'u2:2'}}
        end
        if path == '/api/services/s/photos/u2:2/preview' then
            assert(method == 'PUT' and data == 'jpeg' and media == 'image/jpeg')
            test.uploaded = true
            return {}
        end
        if path == '/api/services/s/complete' then
            assert(data.import_id == 'append-uuid')
            service.status = 'ready'
            return {}
        end
        error('Unexpected HTTP ' .. method .. ' ' .. path)
    end
    package.loaded.Common = common
    package.loaded.Guide = {button=function() return {} end}
    ''')
    lua.globals().package.loaded.Selection = lua.execute((PLUGIN / 'Selection.lua').read_text())
    lua.execute((PLUGIN / 'Prepare.lua').read_text())
    assert lua.globals().test.uploaded and lua.globals().test.opened
    lua.execute((PLUGIN / 'Show.lua').read_text())
    assert lua.globals().test.selected


@pytest.mark.parametrize('accept', [True, False])
def test_local_connection_discovery_still_requires_dialog_confirmation(accept):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().accept = accept
    lua.execute(r'''
        test = {stored=false,requested=false,opened=false}
        local token = 'synthetic-local-connection-token'
        local props
        local view = {}
        for _, name in ipairs({'column','static_text','password_field'}) do
            view[name] = function(_, value) return value end
        end
        local sdk = {
            LrBinding={makePropertyTable=function() props={};return props end},
            LrView={osFactory=function() return view end,bind=function(x) return x end},
            LrPathUtils={getStandardFilePath=function(kind) assert(kind=='home');return '/synthetic/home' end,
                         child=function(parent,child) return parent .. '/' .. child end},
            LrFileUtils={exists=function(path)
                assert(path=='/synthetic/home/Library/Application Support/LrC Photo Selection EN/connection-token');return 'file'
            end,readFile=function() return token .. '\n' end},
            LrDialogs={presentModalDialog=function()
                assert(props.token==token)
                return accept and 'ok' or 'cancel'
            end},
        }
        function import(name) return assert(sdk[name],name) end
        package.loaded.Common = {
            run=function(_,fn) fn({}) end,
            request=function(method,path,body,media,credential)
                assert(method=='GET' and path=='/api/services' and credential==token)
                test.requested=true
            end,
            saveToken=function(value) assert(value==token);test.stored=true end,
            openBrowser=function(value) assert(value==token);test.opened=true end,
        }
    ''')
    lua.execute((PLUGIN / 'Configure.lua').read_text())
    result = lua.globals().test
    assert result.stored == accept
    assert result.requested == accept
    assert result.opened == accept


def test_xmp_gate_is_bound_and_defensive_without_lua_error():
    result = simulate(xmp=False)
    assert result.writes == 0 and not result.claimed
    assert result.error is None
    assert result.xmpBinding == 'xmpChecked'
    assert result.messageTitle == 'XMP check required'


def test_completion_distinguishes_partial_and_points_to_next_step():
    complete = simulate()
    assert complete.messageTitle == 'Application completed'
    assert 'Show candidates in Lightroom' in complete.message
    partial = simulate(current=3)
    assert partial.messageTitle == 'Application needs review'
    assert '1 to review' in partial.message
