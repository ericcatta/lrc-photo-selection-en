local M = {}
local Common = require 'Common'
local Binding = import 'LrBinding'
local Dialogs = import 'LrDialogs'
local View = import 'LrView'

function M.chooseService(context, registration, label, config)
    local options = {}
    for _, item in ipairs(Common.request('GET', '/api/services')) do
        if item.catalog_id == registration and config.statuses[item.status] and not item.archived then
            options[#options + 1] = {title = item.title, value = item.id}
        end
    end
    assert(#options > 0, 'No ready service is linked to this catalog.')
    local properties = Binding.makePropertyTable(context)
    properties.selected = options[1].value
    local view = View.osFactory()
    local answer = Dialogs.presentModalDialog {
        title = config.title,
        contents = view:column {
            bind_to_object = properties,
            view:static_text { title = 'Catalog: ' .. label },
            view:popup_menu { value = View.bind 'selected', items = options },
        }, actionVerb = config.action, cancelVerb = 'Cancel',
    }
    return answer == 'ok' and Common.key(properties.selected) or nil
end

function M.matches(photo, item)
    return photo and photo.localIdentifier == item.local_id and photo:getRawMetadata('uuid') == item.uuid
end

function M.identify(catalog, items)
    local photos, missing = {}, {}
    for _, item in ipairs(items) do
        local photo = catalog:findPhotoByUuid(item.uuid)
        if M.matches(photo, item) then photos[item.photo_id] = photo else missing[item.local_id] = item end
    end
    if next(missing) then
        for _, photo in ipairs(catalog:getAllPhotos()) do
            local item = missing[photo.localIdentifier]
            if item and M.matches(photo, item) then photos[item.photo_id] = photo end
        end
    end
    return photos
end

return M
