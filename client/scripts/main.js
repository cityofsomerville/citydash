'use strict';
require.config({
    paths: {
        // Dependencies:
        "underscore": "lib/underscore-min",
        "backbone": "lib/backbone",
        "leaflet": "http://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.3/leaflet",
        "jquery": "http://code.jquery.com/jquery-1.11.3.min",

        // Utilities:
        "utils": "src/utils",

        // APIs:
        "arcgis": "src/api/arcgis",

        // Application: //
        "config": "src/config",
        "local-config": "src/localConfig",
        "routes": "src/routes",
        "ref-location": "src/refLocation",

        // Map Layers:
        "layers": "src/layerdata/layers",

        // Backbone Models:
        "permit": "src/model/permit",

        // Backbone Collections:
        "permits": "src/model/permits",

        // Backbone Views:
        "permits-view": "src/view/permits",
        "permit-view": "src/view/permit",
        "filters-view": "src/view/filters",
        "map-view": "src/view/map",
        "popup-view": "src/view/popup",
        "ref-marker": "src/leaflet/refMarker",

        "collapsible-view": "src/view/collapsible",
        "spga-filter-view": "src/view/spgaFilter",
        "type-filter-view": "src/view/typeFilter",

        "setup": "src/setup"
    },

    shim: {
        "leaflet": {
            exports: "L"
        }
    }
});

require(["setup"], function(setup) {
    setup.start();

    console.log("Setup complete.");
});
