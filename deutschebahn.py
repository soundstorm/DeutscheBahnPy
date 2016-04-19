#!/usr/bin/env python

try:
	import xmltodict
except ImportError:
	raise ImportError("Install xmltodict from https://github.com/martinblech/xmltodict")
import sys, urllib, urllib2, types

def URLRequest(url, params, method="GET"):
	vers = sys.version_info
	try:
		if (sys.version_info > (3, 0)):
			if not isinstance(params, types.StringTypes):
				params = urllib.parse.urlencode(params)
			if method == "POST":
				f = urllib2.request.urlopen(url, params, timeout=10)
			else:
				f = urllib2.request.urlopen(url+'?'+params, None, timeout=10)
			return f.read().decode(f.info().get_content_charset('UTF-8'))
		else:
			if not isinstance(params, types.StringTypes):
				params = urllib.urlencode(params)
			if method == "POST":
				f = urllib2.urlopen(url, params, timeout=10)
			else:
				f = urllib2.urlopen(url+'?'+params, None, timeout=10)
			return f.read()
	except Exception, e:
		return None


def requestStation(stationName=None, address=None, poi=None, latitude=0, longitude=0, maxDist=500, max=10):
	if stationName != None:
		type = "ST"
		match = stationName
	elif address != None:
		type="ADR"
		match = address
	if stationName != None or address != None:
		req = '<?xml version="1.0" encoding="utf-8" ?><ReqC ver="1.1" prod="String" lang="DE"><LocValReq id="001" maxNr="'+str(max)+'" sMode="1"><ReqLoc type="'+type+'" match="'+match+'" /></LocValReq></ReqC>'
		ret = URLRequest("http://reiseauskunft.bahn.de/bin/query.exe/dn", req, "POST")
		if ret == None:
			return None
		xml = xmltodict.parse(ret)["ResC"]["LocValRes"]
		if hasattr(xml,"Station"):
			stations = list()
			if not isinstance(xml["Station"], list):
				xml["Station"] = (xml["Station"],)
			for station in xml["Station"]:
				stations.append({
				"name":station["@name"],
				"latitude":float(station["@y"])/1000000,
				"longitude":float(station["@x"])/1000000,
				"id":int(station["@externalStationNr"]),
				"type":station["@type"]
				})
			return(stations)
		if hasattr(xml,"Address"):
			addresses = list()
			if not isinstance(xml["Address"], list):
				xml["Address"] = (xml["Address"],)
			for address in xml["Address"]:
				addresses.append({
				"name":address["@name"],
				"latitude":float(address["@y"])/1000000,
				"longitude":float(address["@x"])/1000000,
				"type":address["@type"]
				})
			return addresses
		if hasattr(xml,"Poi"):
			pois = list()
			if not isinstance(xml["Poi"], list):
				xml["Poi"] = (xml["Poi"],)
			for poi in xml["Poi"]:
				pois.append({
				"name":poi["@name"],
				"latitude":float(poi["@y"])/1000000,
				"longitude":float(poi["@x"])/1000000,
				"type":poi["@type"]
				})
			return pois
		return None
	else:
		ret = URLRequest("https://reiseauskunft.bahn.de/bin/query.exe/dol", {"performLocating":2,"L":"vs_java","look_x":longitude*1000000,"look_y":latitude*1000000,"look_maxdist":str(maxDist),"look_nv":"del_doppelt%7Cyes","look_maxn%20o":max})
		if ret == None:
			return None
		xml = xmltodict.parse(ret)["ResC"]["MLcRes"]
		if not isinstance(xml["MLc"], list):
			xml["MLc"] = (xml["MLc"],)
		stations = list()
		for station in xml["MLc"]:
			stations.append({
			"name":station["@n"],
			"latitude":float(station["@y"])/1000000,
			"longitude":float(station["@x"])/1000000,
			"distance":int(station["@dist"]),
			"id":int(station["@externalId"]),
			"type":station["@t"],
			"class":station["@class"]
			})
		return stations

#productsFilter
#ICE,IC/CNL,IR/Schnellzug,Regional-/Nahverkehr,S-Bahn,Bus,Schiff,U-Bahn,Strassenbahn,AS-Taxi,1111
def stationBoard(id, boardType="dep", productsFilter="11111111111111", time="actual", date=None, max=10):
	req = {
	"productsFilter":productsFilter,
	"maxJourneys":max,
	"time":time,
	"input":id,
	"boardType":boardType,
	"L":"vs_java3",
	"start":"yes"
	}
	if date != None:
		req["date"] = date
	ret = URLRequest("http://reiseauskunft.bahn.de/bin/stboard.exe/dn", req)
	if ret == None:
		return None
	xml = xmltodict.parse('<?xml version="1.0" encoding="ISO-8859-1"?><response>'+ret+'</response>')["response"]
	journeys = list()
	if not isinstance(xml["Journey"], list):
		xml["Journey"] = (xml["Journey"],)
	for journey in xml["Journey"]:
		journeys.append({
		"time":journey["@fpTime"],
		"date":journey["@fpDate"],
		"delay":journey["@delay"],
		"delayReason":journey["@delayReason"],
		"approxDelay":journey["@approxDelay"],
		"target":journey["@targetLoc"],
		"direction":journey["@dir"],
		"directionNr":journey["@dirnr"],
		"product":journey["@prod"],
		})
	return(journeys)
		
#EXAMPLE
#stations = requestStation(latitude=52.371728, longitude=9.720859)
#print stationBoard(stations[0]["id"])
#print requestStation(address="Bahnhofsstrasse, Hannover")