-- Offline guide: no Common module, catalog, backend or token is required.
local Dialogs = import 'LrDialogs'
local View = import 'LrView'
local data = require 'GuideData'
local M = {}

function M.show()
    local view = View.osFactory()
    local content = { spacing = 12, width = 640 }
    content[#content + 1] = view:static_text { title = data.intro, width_in_chars = 85, height_in_lines = 2 }
    for index, step in ipairs(data.steps) do
        content[#content + 1] = view:static_text { title = index .. '. ' .. step.title, font = '<system/bold>' }
        content[#content + 1] = view:static_text { title = step.body, width_in_chars = 85, height_in_lines = math.ceil(#step.body / 75) + 1 }
    end
    for _, note in ipairs(data.notes) do
        content[#content + 1] = view:static_text { title = note.title, font = '<system/bold>' }
        content[#content + 1] = view:static_text { title = note.body, width_in_chars = 85, height_in_lines = math.ceil(#note.body / 75) + 1 }
    end
    Dialogs.presentModalDialog {
        title = data.title,
        contents = view:scrolled_view { width = 680, height = 520, view:column(content) },
        actionVerb = 'Close guide', cancelVerb = '< exclude >',
    }
end

function M.button()
    return View.osFactory():push_button { title = 'Guide', action = function() M.show() end }
end

return M
