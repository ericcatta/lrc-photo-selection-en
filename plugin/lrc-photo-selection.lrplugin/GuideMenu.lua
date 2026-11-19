local Context = import 'LrFunctionContext'
Context.postAsyncTaskWithContext('Photo selection guide', function()
    require('Guide').show()
end)
