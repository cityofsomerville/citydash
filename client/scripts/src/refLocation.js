/*
 * The reference location is used to determine the distance to
 */
define(["backbone", "lib/leaflet", "view/alerts", "config", "api/arcgis",
        "collection/regions", "utils", "appState"],
       function(B, L, alerts, config, arcgis, regions, $u, appState) {
           var bounds;

           var LocationModel = B.Model.extend({
               defaults: {
                   lat: config.refPointDefault.lat,
                   lng: config.refPointDefault.lng,
                   // The search radius, centered on the current latitude and longitude:
                   r: config.minSubscribeRadius,
                   // Typical values:
                   //  - "auto": using the default coords
                   //  - "geolocate": set from the user's browser
                   //  - "map": set by double-clicking the map
                   //  - "address": set from a geocoded address
                   setMethod: "auto"
               },

               initialize: function(attrs, options) {
                   var ref = appState.getKey("ref");

                   B.Model.prototype.initialize.call(
                       this, this.checkedAttrs(ref, attrs), options);
                   this.bounds = null;

                   appState.onStateKeyChange("ref", this.checkedSet, this);
               },

               checkedAttrs: function(ref, attrs) {
                   var lat = parseFloat(ref.lat),
                       lng = parseFloat(ref.lng),
                       r = parseInt(ref.r),
                       change = {};

                   if (!isNaN(lat) && !isNaN(lng)) {
                       change = {lat: lat, lng: lng};
                   }

                   if (!isNaN(r)) {
                       change.r = Math.max(config.minSubscribeRadius, Math.min(config.maxSubscribeRadius, r));
                   }

                   return (!_.isEmpty(change)) ? _.extend({}, ref, change) : null;
               },

               checkedSet: function(ref, oldRef) {
                   var attrs = this.checkedAttrs(ref);

                   if (attrs) {
                       this.set(attrs);
                   }
               },

               getPoint: function() {
                   return [this.get("lat"), this.get("lng")];
               },

               getLatLng: function() {
                   return L.latLng(this.get("lat"), this.get("lng"));
               },

               radiusConfigurable: function() {
                   return config.minSubscribeRadius &&
                       config.minSubscribeRadius !== config.maxSubscribeRadius;
               },

               getRadiusMeters: function() {
                   var r = this.get("r");
                   return r && $u.feetToM(r);
               },

               /**
                * Set the latitude and longitude using the browser's
                * geolocation features, if available.
                */
               setFromBrowser: function() {
                   this.set("geolocating", true);

                   var self = this,
                       promise = $u.promiseLocation(),
                       timeout = setTimeout(function() {
                           alerts.showNamed("geolocSlow", "geolocError", {},
                                            {buttons: {
                                                cancel: {
                                                    label: "Cancel Geolocation",
                                                    handler: function() {
                                                        promise.reject();
                                                        return true;
                                                    }
                                                }
                                            }});
                       }, 6000);

                   return promise.then(function(loc) {
                           if (bounds && !bounds.contains(loc)) {
                               alerts.showNamed("geolocNotInBounds", "geolocError",
                                                {region:  regions.getSelectionDescription()});
                               return $.Deferred().reject([loc]);
                           } else {
                               alerts.dismissMessage("geolocError");
                           }

                           appState.setHashKey("ref", {
                               lat: loc[0],
                               lng: loc[1],
                               setMethod: "geolocate"
                           });

                           return loc;
                       }, function(err) {
                           if (err && err.reason) {
                               alerts.show(err.reason, "error", null, "geolocError");
                           } else {
                               alerts.dismissMessage("geolocError");
                           }
                       })
                       .always(function() {
                           clearTimeout(timeout);
                           self.set("geolocating", false);
                       });
               },

               setFromLatLng: function(lat, long, address) {
                   if (bounds && !bounds.contains([lat, long])) {
                       return false;
                   }

                   appState.setHashKey("ref", {
                       lat: lat,
                       lng: long,
                       setMethod: address ? "address" : "map",
                       address: address || "",
                       r: this.defaults.r !== this.get("r") ? this.get("r") : this.defaults.r
                   }, null, true);

                   return true;
               },

               setFromAddress: function(addr) {
                   var self = this;
                   this.set("geolocating", true);
                   alerts.dismissMessage("geoloc_error");
                   return arcgis.geocode(addr).then(arcgis.getLatLngForFirstAddress).done(function(loc) {
                       if (bounds && !bounds.contains(loc)) {
                           alerts.showNamed("addressNotInBounds", "geolocError",
                                            {region: regions.getSelectionDescription()});
                           return loc;
                       } else {
                           alerts.dismissMessage("geolocError");
                       }

                       appState.setHashKey("ref", {
                           address: loc[2].ShortLabel || addr,
                           enteredAddress: addr,
                           setMethod: "address",
                           lat: loc[0],
                           lng: loc[1]
                       });

                       return loc;
                   }).fail(function() {
                       alerts.showNamed("addressNotFound", "geolocError");
                   }).always(function() {
                       self.set("geolocating", false);
                   });
               }
           });

           var refLocation = new LocationModel();

           // TODO: Update whenever the active regions change:
           refLocation
               .listenTo(regions, "regionBounds",
                         function(newBounds) {
                             bounds = newBounds;
                         })
               .listenTo(regions, "selectionRemoved",
                         function(regions, ids) {});

           return refLocation;
       });
