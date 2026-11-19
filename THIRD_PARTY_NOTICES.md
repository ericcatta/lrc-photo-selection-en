# Third-party components

`plugin/lrc-photo-selection.lrplugin/JSON.lua` derives from rxi/json.lua v0.1.2,
Copyright (c) 2019 rxi. The complete MIT license is included in that file. The local
change formats numbers with 17 rather than 14 significant digits to preserve
Lightroom timestamps during JSON exchange.

Source: https://github.com/rxi/json.lua/tree/v0.1.2

React, React DOM and scheduler are MIT-licensed npm dependencies. Their licenses
are included in the packages and in distribution assets by the build. Python
dependencies are installed through pip; their source code is not embedded in this
repository. The Adobe SDK is not redistributed. No AI weights are distributed.
