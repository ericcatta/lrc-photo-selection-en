local Common = require 'Common'
local Selection = require 'Selection'
local Dialogs = import 'LrDialogs'

Common.run('Show candidates', function(context)
    local catalog, path, label = Common.catalog()
    local registration = Common.registration(path, false)
    local sid = Selection.chooseService(context, registration, label, {
        title = 'Show candidates', action = 'Select in Lightroom', statuses = {ready = true},
    })
    if not sid then return end
    local service = Common.request('GET', '/api/services/' .. sid)
    assert(service.id == sid and service.catalog_id == registration and service.status == 'ready' and not service.archived,
        'The service is unavailable in this catalog.')
    local byID, items = {}, {}
    for _, item in ipairs(service.photos) do byID[item.id] = item end
    for _, id in ipairs(service.selected_ids) do
        local item = assert(byID[id], 'Invalid candidate identifier.')
        items[#items + 1] = {photo_id = id, uuid = item.uuid, local_id = item.local_id}
    end
    if #items == 0 then
        Dialogs.message('No candidates', 'The service has no candidates to select.', 'info')
        return
    end
    local photos = Selection.identify(catalog, items)
    local active, others, expected = nil, {}, {}
    for _, item in ipairs(items) do
        local photo = photos[item.photo_id]
        if photo then
            expected[photo.localIdentifier] = true
            if active then others[#others + 1] = photo else active = photo end
        end
    end
    assert(active, 'No candidates were found in the active catalog.')
    Common.assertCatalog(path)
    catalog:setSelectedPhotos(active, others)
    local matched = 0
    if catalog:getTargetPhoto() then
        for _, photo in ipairs(catalog:getTargetPhotos()) do
            if expected[photo.localIdentifier] then matched = matched + 1 end
        end
    end
    if matched ~= #items then
        Dialogs.message('Partial selection', matched .. ' of ' .. #items .. ' candidates selected. Check the active sources and filters, then try again.', 'warning')
    end
end)
