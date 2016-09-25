function initMap() {
    querylat=parseFloat(getParameterByName("lat"));
    querylng=parseFloat(getParameterByName("lng"));
    if (querylat) lat=querylat;
    if (querylng) lng=querylng;
    map = new google.maps.Map(document.getElementById('map'), {
        center: {
            lat: lat,
            lng: lng
        },
        zoom: 15,
        disableDoubleClickZoom: true,
        streetViewControl: false
    });
    getFile("static/" + language + ".json", false, function(tnames) {
        pokenames = JSON.parse(tnames);
    });
    if (language == "german") {
        timeuntiltext = "bis";
        timelefttext = "Zeit &#252;brig: ";
        timehiddentext = "Versteckt f&#252;r: ";
        timehiddentext_15min = "(danach zur&#252;ck f&#252;r 15m)";
        timehiddentext_30min = "(danach zur&#252;ck f&#252;r 30m)";
        timereturntext_15min_15min = "(15m danach zur&#252;ck f&#252;r 15m)";
        timereturntext_15min_30min = "(15m danach zur&#252;ck f&#252;r 30m)";
        timereturntext_30min_15min = "(30m danach zur&#252;ck f&#252;r 15m)";
    } else if (language == "english") {
        timeuntiltext = "until";
        timelefttext = "Time left: ";
        timehiddentext = "Hidden for: ";
        timehiddentext_15min = "(then back for 15m)";
        timehiddentext_30min = "(then back for 30m)";
        timereturntext_15min_15min = "(15m later back for 15m)";
        timereturntext_15min_30min = "(15m later back for 30m)";
        timereturntext_30min_15min = "(30m later back for 15m)";
    } else if(language == "spanish") {
        timeuntiltext = "hasta";
        timelefttext = "Tiempo restante: ";
        timehiddentext = "Oculto por: ";
        timehiddentext_15min = "(volvera por 15m)";
        timehiddentext_30min = "(volvera por 30m)";
        timereturntext_15min_15min = "(15m volvera mas tarde por 15m)";
        timereturntext_15min_30min = "(15m volvera mas tarde por 30m)";
        timereturntext_30min_15min = "(30m volvera mas tarde por 15m)";
    }
    // filter interface
    pokefilter = getCookie("pokefilter");
    datatill = parseInt(localStorage.getItem('datatill' + profile));
    if (datatill === null)
        datatill = 0;

    wholedata = JSON.parse(localStorage.getItem('pokedata' + profile));
    if (wholedata === null)
        wholedata = [];
    cleanWholedata();
    document.getElementById("filterdialog").style.display = "none";

    var div = document.createElement("div");
    div.innerHTML = "active";
    div.id = "filter_active";
    div.style.opacity = 1;
    var callback = filt_toogle
    div.addEventListener("click", callback, false)
    document.getElementById("filterdialog").appendChild(div);

    var div = document.createElement("div");
    div.innerHTML = "show all";
    div.id = "filter_show_a";
    var callback = filt_show_all
    div.addEventListener("click", callback, false)
    document.getElementById("filterdialog").appendChild(div);

    var div = document.createElement("div");
    div.innerHTML = "hide all";
    div.id = "filter_hide_a";
    var callback = filt_hide_all
    div.addEventListener("click", callback, false)
    document.getElementById("filterdialog").appendChild(div);

    var callback = function() {
        if (this.style.opacity < 1)
            this.style.opacity = 1;
        else
            this.style.opacity = 0.5;
        updateFilter();
    }
    for (var i = 1; i < 152; i++) {
        var div = document.createElement("div");
        div.innerHTML = "[" + i + "] " + pokenames[i];
        if (filteredOut(i))
            div.style.opacity = 0.5;
        else
            div.style.opacity = 1;
        div.id = "filter" + i;
        div.addEventListener("click", callback, false)
        document.getElementById("filterdialog").appendChild(div);
    }

    currentLocationMarker = new google.maps.Marker();
    infowindow = new google.maps.InfoWindow();
    iconSize = new google.maps.Size(icsize_scaled, icsize_scaled);
    iconAnchor = new google.maps.Point(Math.round(icsize_scaled / 2), Math.round(icsize_scaled / 2));
    iconScaledSize = new google.maps.Size(icsize_scaled, 151 * icsize_scaled);

    google.maps.event.addListener(map, 'click', function(event) {
        infowindow.close()
        var dialog = document.getElementById("filterdialog");
        if (dialog.style.display == "inherit")
            dialog.style.display = "none";
    });
    google.maps.event.addListener(map, 'bounds_changed', showMarkers);
    startup = setInterval(f_startup, 1000)
}

function getFile(path, asynch, callback) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", path, asynch);
    xhr.onload = function(e) {
        if (xhr.readyState === 4 && xhr.status === 200) {
            callback(xhr.responseText);
        }
    };
    xhr.send(null);
}

debug = 0;

function useData(newData) {
    // Add updated markers
    for (var i = 0; i < newData.length; i++) {
        var timenow = Math.round((new Date()).getTime() / 1000);
        p_spawnid = newData[i][0];
        p_latitude = newData[i][1];
        p_longitude = newData[i][2];
        p_addinfo = newData[i][3];
        p_pokeid = newData[i][4];
        p_expiretime = newData[i][5];

        var timeleft = p_expiretime - timenow;
        if (timeleft > 0) {
            var newaddinfo = p_addinfo;
            var cIcon = {
                url: "static/icons/" + icon_set,
                size: iconSize,
                origin: new google.maps.Point(0, icsize_scaled * (p_pokeid - 1)),
                anchor: iconAnchor,
                scaledSize: iconScaledSize
            };
            var s = 0;
            while (s < spawns.length && spawns[s] != p_spawnid) {
                s++;
            }
            if (s < spawns.length) {
                if (markers[s].validTill != p_expiretime) {
                    if (markers[s].validTill == 0 || markers[s].id != p_pokeid) {
                        markers[s].id = p_pokeid;
                        markers[s].icon = cIcon;
                        markers[s].setOpacity(1.0);
                        markers[s].addinfo = newaddinfo;
                    }
                    markers[s].validTill = p_expiretime;
                }
            } else {
                var marker = new MarkerWithLabel({
                    position: {
                        lat: p_latitude,
                        lng: p_longitude
                    },
                    labelContent: "",
                    labelAnchor: new google.maps.Point(30, -30),
                    labelClass: "label",
                    optimized: false,
                    id: p_pokeid,
                    validTill: p_expiretime,
                    spawnID: p_spawnid,
                    icon: cIcon,
                    addinfo: newaddinfo
                });
                marker.addListener('click', function() {
                    infowindow.close();
                    infowindow.setContent(this.infotext);
                    infowindow.open(map, this);
                });
                marker.addListener('dblclick', function() {
                    if (this.getOpacity() == 0.5)
                        this.setOpacity(1);
                    else
                        this.setOpacity(0.5);
                });

                markers.push(marker);
                spawns.push(p_spawnid);
            }
        }
    }
    // Update info text of markers and clear void ones
    for (var i = 0; i < markers.length; i++) {
        if (markers[i].validTill != 0) {
            var timeleft = markers[i].validTill - timenow;
            var ishidden = false;
            var backmsg = "";
            var firstmsg = "";

            if (timeleft > 0) {
                switch(markers[i].addinfo) { // addinfo = spawntype
                    case 0:
                        backmsg = "";
                        ishidden = false;
                        break;
                    case 1: // SPAWN_2x15 (Spawntime 45min & hidden between min 30-15)
                        if (timeleft > 1800){ // > 30min
                            timeleft -= 1800;
                            backmsg = timereturntext_15min_15min;
                        }else if(timeleft > 900){ // > 15min
                            timeleft -= 900;
                            ishidden = true;
                            backmsg = timehiddentext_15min;
                        }
                        break;
                    case 2: // SPAWN_1x60h2 (Spawntime 60min & hidden between min 45-30)
                        if (timeleft > 2700){ // > 45min
                            timeleft -= 2700;
                            backmsg = timereturntext_15min_30min;
                        }else if(timeleft > 1800){ // > 30min
                            timeleft -= 1800;
                            ishidden = true;
                            backmsg = timehiddentext_30min;
                        }
                        break;
                    case 3: // SPAWN_1x60h3 (Spawntime 60min & hidden between min 30-15)
                        if (timeleft > 1800){ // > 30min
                            timeleft -= 1800;
                            backmsg = timereturntext_15min_15min;
                        }else if(timeleft > 900){ // > 15min
                            timeleft -= 900;
                            ishidden = true;
                            backmsg = timehiddentext_15min;
                        }
                        break;
                    case 4: // SPAWN_1x60h23 (Spawntime 60min & hidden between min 45-30 and 30-15)
                        if (timeleft > 2700){ // > 45min
                            timeleft -= 2700;
                            backmsg = timereturntext_30min_15min;
                        }else if(timeleft > 900) { // > 15min
                            timeleft -= 900;
                            ishidden = true;
                            backmsg = timehiddentext_15min;
                        }
                        break;
                    default:
                        backmsg = "";
                        ishidden = false;
                }

                /* Marker infotext
                 * 1. Line: Pokemonname
                 * (2. Line: backmsg)
                 * 3. Line: Countdown*/
                firstmsg = "<span class='label_pokemon_name'>" + pokenames[markers[i].id] + " (" + markers[i].id + ") <a target=\"_new\" href=\"https://maps.google.com/maps?q=" + markers[i].position.lat() + "," + markers[i].position.lng() + "\"><img src=\"static/icons/map.svg\" width=12 height=12></a></span>";
				timemsg = new Date(markers[i].validTill * 1000)
				timemsg = "<span class='label_expire_time'>&ensp;" + timeuntiltext + " " + padZero(timemsg.getHours())+":" + padZero(timemsg.getMinutes()) + ":" + padZero(timemsg.getSeconds()) + "</span>"
                if (backmsg != ""){
                    backmsg = "<span class='label_line'>" + backmsg + "</span>";
                }
                if (ishidden == false){ // different format if the pokemon is hidden
                    markers[i].infotext = firstmsg + "<span class='label_line'>" + timelefttext + formatTimeleftString(timeleft) + "</span>" + timemsg + backmsg;
                    markers[i].labelClass = "label";
                }else{
                    markers[i].infotext = "<span class='label_hidden_pokemon'>";
                    markers[i].infotext += firstmsg + "<span class='label_line'>" + timehiddentext + formatTimeleftString(timeleft) + "</span>" + timemsg + backmsg;
                    markers[i].infotext += "</span>";
                    markers[i].labelClass = "hidden_label";
                }
                markers[i].labelContent = formatTimeleftString(timeleft);
				
            } else {
                markers[i].validTill = 0;
            }
        }
    }
    file_succ = true;
    showMarkers();
}

function padZero(number) {
    if (number < 10) { return "0"+String(number)} else {return String(number)}
}

function formatTimeleftString(timeleft){
    return Math.floor(timeleft / 60) + "m " + (timeleft % 60) + "s"
}

function cleanWholedata() {
    var timenow = Math.round((new Date()).getTime() / 1000);
    wholedata = wholedata.filter(function(entry) {return entry[5] > timenow});
    localStorage.setItem('pokedata' + profile, JSON.stringify(wholedata));
    localStorage.setItem('datatill' + profile, datatill.toString());
}

function refreshData() {
    $.getJSON('_getdata', {
        data_till: datatill,
        profile: profile
    }, function(data, status) {
        datatill = data[0];
        wholedata = wholedata.concat(data[1]);
        if (clean_c > 3) {
            clean_c = 0;
            cleanWholedata();
        }
        useData(wholedata);
    });
}

function showMarkers() {
    changing = false;
    var bounds = map.getBounds();
    var timenow = Math.round((new Date()).getTime() / 1000);
    var filt_inactive = (document.getElementById("filter_active").style.opacity < 1)

    for (var i = 0; i < markers.length; i++) {
        if (bounds.contains(markers[i].getPosition()) && markers[i].validTill - timenow > 0 && (filt_inactive || !filteredOut(markers[i].id))) {
            if (markers[i].map === null)
                markers[i].setMap(map);
			markers[i].label.setStyles();
			markers[i].label.setContent();
			markers[i].labelVisible = showCdn;
			markers[i].label.setVisible();
        } else {
            markers[i].setMap(null);
        }
    }
    anchor = infowindow.get('anchor');
    if (anchor != undefined && anchor !== null) {
        infowindow.setContent(anchor.infotext);
    }
}

function f_startup() {
    if (~changing) {
        clearInterval(startup);
        useData(wholedata);
        refreshData();
        cleanWholedata();
        setInterval(refreshData, 10000);
    }
}

function findLocation() {
    if (navigator.geolocation)
        navigator.geolocation.getCurrentPosition(function(position) {
            var latlng = new google.maps.LatLng(position.coords.latitude, position.coords.longitude);
            currentLocationMarker.setPosition(latlng);
            if (currentLocationMarker.map !== null)
                currentLocationMarker.setMap(null);
            currentLocationMarker.setAnimation(google.maps.Animation.DROP);
            currentLocationMarker.setMap(map);
            if (!map.getBounds().contains(latlng))
                map.panTo(latlng)
        }, function(error) {
            alert(error.message)
        });
}

function showCountdown(){
    showCdn = !showCdn;
    showMarkers()
}

function filt_toogle() {
    if (this.style.opacity < 1) {
        this.style.opacity = 1;
        this.innerHTML = "active";
    } else {
        this.style.opacity = 0.5;
        this.innerHTML = "inactive";
    }
    showMarkers()
}

function filt_show_all() {
    pokefilter = ",";
    for (var i = 1; i < 152; i++) {
        var entry = document.getElementById("filter" + i)
        if (entry.style.opacity < 1) {
            entry.style.opacity = 1;
        }
    }
    setCookie('pokefilter', pokefilter);
    showMarkers();
}

function filt_hide_all() {
    pokefilter = ",";
    for (var i = 1; i < 152; i++) {
        pokefilter = pokefilter + i + ','
        var entry = document.getElementById("filter" + i)
        if (entry.style.opacity == 1) {
            entry.style.opacity = 0.5;
        }
    }
    setCookie('pokefilter', pokefilter);
    showMarkers();
}

function setCookie(name, value) {
    var d = new Date(21474800000000);
    document.cookie = name + '=' + value + "; expires=" + d.toUTCString();;
}

function getCookie(name) {
    var chunks = document.cookie.split(";");
    for (var i = 0; i < chunks.length; i++) {
        ind = chunks[i].indexOf(name + "=");
        if (ind > -1) {
            return chunks[i].substr(ind + name.length + 1)
        }
    }
    return -1
}

function updateFilter() {
    pokefilter = ",";
    for (var i = 1; i < 152; i++) {
        if (document.getElementById("filter" + i).style.opacity < 1) {
            pokefilter = pokefilter + i + ','
        }
    }
    setCookie('pokefilter', pokefilter);
    showMarkers();
}

function filteredOut(id) {
    var filtertest = "," + pokefilter + ",";
    return (filtertest.indexOf("," + id + ",") > -1)
}

function showFilterDialog() {
    var dialog = document.getElementById("filterdialog");
    if (dialog.style.display == "none") {
        dialog.style.display = "inherit";
    } else {
        dialog.style.display = "none";
    };
}

function getParameterByName(name, url) {
    if (!url) url = window.location.href;
    name = name.replace(/[\[\]]/g, "\\$&");
    var regex = new RegExp("[?&]" + name + "(=([^&#]*)|&|#|$)"),
        results = regex.exec(url);
    if (!results) return null;
    if (!results[2]) return '';
    return decodeURIComponent(results[2].replace(/\+/g, " "));
}