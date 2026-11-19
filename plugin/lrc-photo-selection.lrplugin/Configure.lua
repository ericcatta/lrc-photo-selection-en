local Common = require 'Common'
local Binding = import 'LrBinding'
local Dialogs = import 'LrDialogs'
local View = import 'LrView'
local Path = import 'LrPathUtils'
local File = import 'LrFileUtils'
Common.run('Configure local connection', function(context)
    local properties = Binding.makePropertyTable(context)
    local connectionFile = Path.child(Path.child(Path.child(Path.child(Path.getStandardFilePath('home'), 'Library'), 'Application Support'), 'LrC Photo Selection EN'), 'connection-token')
    local localToken = File.exists(connectionFile) == 'file' and File.readFile(connectionFile) or ''
    properties.token = type(localToken) == 'string' and localToken:match('^%s*([%w_-]+)%s*$') or ''
    properties.token = properties.token or ''
    local view = View.osFactory()
    local answer = Dialogs.presentModalDialog {
        title = 'Connect to the local web app',
        contents = view:column {
            bind_to_object = properties,
            view:static_text { title = properties.token ~= '' and 'Local connection found. Confirm to connect the plugin.' or 'Paste the token shown by the backend startup command.' },
            view:password_field { value = View.bind 'token', width_in_chars = 48 },
        }, actionVerb = 'Connect', cancelVerb = 'Cancel',
    }
    if answer ~= 'ok' then return end
    local token = properties.token:match('^%s*(.-)%s*$')
    Common.request('GET', '/api/services', nil, nil, token)
    Common.saveToken(token)
    Common.openBrowser(token)
end)
