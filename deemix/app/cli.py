#!/usr/bin/env python3
from deemix.api.deezer import Deezer
import deemix.utils.localpaths as localpaths
from deemix.utils.misc import getIDFromLink, getTypeFromLink, getBitrateInt
from deemix.app.downloader import download_track, download_album, download_playlist, download_artist, download_spotifytrack, download_spotifyalbum
from os import system as execute
import os.path as path
from os import mkdir

dz = Deezer()

def requestValidArl():
	while True:
		arl = input("Paste here your arl:")
		if dz.login_via_arl(arl):
			break
	return arl

def login():
	configFolder = localpaths.getConfigFolder()
	if not path.isdir(configFolder):
		mkdir(configFolder)
	if path.isfile(path.join(configFolder, '.arl')):
		with open(path.join(configFolder, '.arl'), 'r') as f:
			arl = f.read()
		if not dz.login_via_arl(arl):
			arl = requestValidArl()
	else:
		arl = requestValidArl()
	with open(path.join(configFolder, '.arl'), 'w') as f:
		f.write(arl)

def downloadLink(url, settings, bitrate=None):
	forcedBitrate = getBitrateInt(bitrate)
	type = getTypeFromLink(url)
	id = getIDFromLink(url, type)
	folder = settings['downloadLocation']
	if type == None or id == None:
		print("URL not recognized")
	if type == "track":
		folder = download_track(dz, id, settings, forcedBitrate)
	elif type == "album":
		folder = download_album(dz, id, settings, forcedBitrate)
	elif type == "playlist":
		folder = download_playlist(dz, id, settings, forcedBitrate)
	elif type == "artist":
		download_artist(dz, id, settings, forcedBitrate)
	elif type == "spotifytrack":
		folder = download_spotifytrack(dz, id, settings, forcedBitrate)
	elif type == "spotifyalbum":
		folder = download_spotifyalbum(dz, id, settings, forcedBitrate)
	else:
		print("URL not supported yet")
		return None
	if settings['executeCommand'] != "":
		execute(settings['executeCommand'].replace("%folder%", folder))
