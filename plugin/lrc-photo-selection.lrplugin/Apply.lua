local Common = require 'Common'
local Binding = import 'LrBinding'
local Dialogs = import 'LrDialogs'
local Progress = import 'LrProgressScope'
local View = import 'LrView'

local Selection = require 'Selection'
local Guide = require 'Guide'

local function confirmPlan(context, service, plan, label, byID)
    local properties = Binding.makePropertyTable(context)
    properties.xmpChecked = false
    local lines = {}
    for _, item in ipairs(plan.items) do
        local filename = byID[item.photo_id].filename or item.photo_id
        lines[#lines + 1] = filename:gsub('%c', ' ') .. ' [' .. item.photo_id .. '] · 0 → 1'
    end
    properties.operations = table.concat(lines, '\n')
    local view = View.osFactory()
    local answer = Dialogs.presentModalDialog {
        title = 'Confirm star application',
        contents = view:column {
            bind_to_object = properties,
            view:static_text { title = 'Catalog: ' .. label },
            view:static_text { title = 'Service: ' .. service.title .. ' (revision ' .. plan.revision .. ')' },
            view:static_text { title = 'Plan ' .. plan.batch_id .. ' · ' .. #plan.items .. ' operations' },
            view:scrolled_view { width = 620, height = 180, view:edit_field { value = View.bind 'operations', width_in_chars = 72, height_in_lines = #lines + 1, enabled = false } },
            view:static_text { title = '1. In Catalog Settings → Metadata, check that automatic XMP writing is disabled.' },
            view:static_text { title = '2. The checkbox below records your check; it does not change Lightroom preferences.' },
            view:checkbox { title = 'I checked that Automatically write changes into XMP is disabled.', value = View.bind 'xmpChecked' },
            Guide.button(),
        }, actionBinding = { enabled = { bind_to_object = properties, key = 'xmpChecked' } }, actionVerb = 'Apply stars', cancelVerb = 'Cancel',
    }
    if answer ~= 'ok' then return false end
    if properties.xmpChecked ~= true then
        Dialogs.message('XMP check required', 'No stars were applied. Check automatic XMP writing in Catalog Settings → Metadata, then reopen Apply stars and select the confirmation checkbox in the plugin.', 'warning')
        return false
    end
    return true
end

local function result(item, status, reason, before, after)
    return {photo_id = item.photo_id, status = status, reason = reason, before = before, after = after}
end

local function applyOne(catalog, path, marker, outcomePath, plan, item, photo, progress)
    local outcome, wrote
    local gate = catalog:withWriteAccessDo('Photo Selection (English): assign one star', function()
        Common.assertCatalog(path)
        outcome = Common.read(outcomePath)
        if outcome then return end
        local prior = Common.read(marker)
        if prior then
            if prior.batch_id == plan.batch_id then
                outcome = result(item, 'uncertain', 'A previous attempt has no verified outcome; the star was not applied again.')
            else
                outcome = result(item, 'skipped', 'A rating change was already attempted for this photograph.')
            end
            return
        end
        if progress:isCanceled() then
            outcome = result(item, 'skipped', 'Application stopped before this photograph.')
            return
        end
        if not Selection.matches(photo, item) then
            outcome = result(item, 'conflict', 'Lightroom identifier not found or ambiguous.')
            return
        end
        local current = photo:getRawMetadata('rating') or 0
        local edited = photo:getRawMetadata('lastEditTime')
        if current ~= 0 or type(edited) ~= 'number' or edited ~= item.expected_edit_time then
            outcome = result(item, 'conflict', 'The rating or edit time differs from the imported state.', current, current)
            return
        end
        Common.write(marker, {batch_id = plan.batch_id})
        photo:setRawMetadata('rating', 1)
        wrote = true
    end, {timeout = 5})
    if gate ~= 'executed' then return result(item, 'skipped', 'Catalog write access is unavailable.') end
    if not wrote then return assert(outcome, 'Rating outcome is unavailable.') end
    local newRating = photo:getRawMetadata('rating') or 0
    if newRating == 1 then return result(item, 'applied', 'One star verified after the change.', 0, 1) end
    return result(item, 'uncertain', 'The star could not be verified after the change.', 0, newRating)
end

Common.run('Apply stars', function(context)
    local catalog, path, label = Common.catalog()
    local registration = Common.registration(path, false)
    local sid = Selection.chooseService(context, registration, label, {
        title = 'Choose a service', action = 'Show plan', statuses = {ready = true, applying = true},
    })
    if not sid then return end
    local endpoint = '/api/services/' .. sid
    local service = Common.request('GET', endpoint)
    local plan = Common.request('GET', endpoint .. '/rating-plan/latest')
    assert(plan.schema_version == 1 and plan.service_id == sid and plan.catalog_id == registration
        and plan.revision == service.revision, 'The plan does not match the catalog or current revision.')
    local batch = Common.key(plan.batch_id)
    local byID, seen = {}, {}
    for _, photo in ipairs(service.photos) do byID[photo.id] = photo end
    for _, item in ipairs(plan.items) do
        local id = Common.key(item.photo_id)
        local imported = byID[id]
        assert(not seen[id] and imported and imported.uuid == item.uuid and imported.local_id == item.local_id
            and imported.baseline_rating == 0 and item.expected_rating == 0 and item.target_rating == 1
            and type(item.expected_edit_time) == 'number' and imported.baseline_edit_time == item.expected_edit_time,
            'The plan contains an invalid operation.')
        seen[id] = true
    end
    if #plan.items == 0 then
        Dialogs.message('No changes', 'The plan contains no ratings to apply.', 'info')
        return
    end
    if not confirmPlan(context, service, plan, label, byID) then return end
    Common.assertCatalog(path)
    local claimed = Common.request('POST', endpoint .. '/rating-plan/claim', {batch_id = batch})
    assert(claimed.ok == true, 'The backend did not reserve the plan.')
    local photos = Selection.identify(catalog, plan.items)
    local progress = Progress { title = 'Applying Lightroom ratings', functionContext = context }
    local results, applied = {}, 0
    for index, item in ipairs(plan.items) do
        Common.assertCatalog(path)
        local outcomePath = Common.file('batch-' .. batch, item.photo_id)
        local outcome = Common.read(outcomePath)
        if not outcome then
            local marker = Common.file('rating-' .. registration, item.photo_id)
            outcome = applyOne(catalog, path, marker, outcomePath, plan, item, photos[item.photo_id], progress)
            local recorded = Common.read(outcomePath)
            if recorded then outcome = recorded else Common.write(outcomePath, outcome) end
        end
        results[#results + 1] = outcome
        if outcome.status == 'applied' then applied = applied + 1 end
        progress:setPortionComplete(index, #plan.items)
    end
    progress:done()
    Common.request('POST', endpoint .. '/rating-receipts', {batch_id = batch, results = results})
    local skipped, review = 0, 0
    for _, outcome in ipairs(results) do
        if outcome.status == 'skipped' then skipped = skipped + 1 end
        if outcome.status == 'conflict' or outcome.status == 'uncertain' then review = review + 1 end
    end
    local complete = applied == #plan.items
    Dialogs.message(complete and 'Application completed' or 'Application needs review',
        tostring(applied) .. ' stars applied out of ' .. #plan.items .. ' planned; '
        .. skipped .. ' skipped; ' .. review .. ' to review.\n'
        .. 'Open Outcome in the web app for the receipt. To view candidates: Library → Plug-in Extras → Show candidates in Lightroom.',
        complete and 'info' or 'warning')
end)
