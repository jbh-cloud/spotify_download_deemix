#!/usr/bin/env python3
from deemix.api.deezer import Deezer, APIError
from deemix.utils.taggers import tagID3, tagFLAC
import json
import re

extensions = {
	9: '.flac',
	3: '.mp3',
	1: '.mp3',
	8: '.mp3',
	15: '.mp4',
	14: '.mp4',
	13: '.mp4'
}

dz = Deezer()

def getIDFromLink(link, type):
	if '?' in link:
		link = link[:link.find('?')]

	if link.startswith("http") and 'open.spotify.com/' in link:
		if type == "spotifyplaylist":
			return link[link.find("/playlist/")+10]
		if type == "spotifytrack":
			return link[link.find("/track/")+7]
		if type == "spotifyalbum":
			return link[link.find("/album/")+7]
	elif link.startswith("spotify:"):
		if type == "spotifyplaylist":
			return link[link.find("playlist:")+9]
		if type == "spotifytrack":
			return link[link.find("track:")+6]
		if type == "spotifyalbum":
			return link[link.find("album:")+6]
	elif type == "artisttop":
		return re.search("\/artist\/(\d+)\/top_track",link)[1]
	else:
		return link[link.rfind("/")+1:]

def getTypeFromLink(link):
	type = ''
	if 'spotify' in link:
		type = 'spotify'
		if 'playlist' in link:
			type += 'playlist'
		elif 'track' in link:
			type += 'track'
		elif 'album' in link:
			type += 'album'
	elif 'deezer' in link:
		if '/track' in link:
			type = 'track'
		elif '/playlist' in link:
			type = 'playlist'
		elif '/album' in link:
			type = 'album'
		elif re.search("\/artist\/(\d+)\/top_track",link):
			type = 'artisttop'
		elif '/artist' in link:
			type = 'artist'
	return type

def getTrackData(id):
	if not id:
		return None
	trackAPI = dz.get_track_gw(id)
	if not 'MD5_ORIGIN' in trackAPI:
		trackAPI['MD5_ORIGIN'] = dz.get_track_MD5(id)

	track = {}
	track['id'] = trackAPI['SNG_ID']
	track['title'] = trackAPI['SNG_TITLE']
	if trackAPI['VERSION']:
		track['title'] += " "+trackAPI['VERSION']
	track['duration'] = trackAPI['DURATION']
	track['MD5'] = trackAPI['MD5_ORIGIN']
	track['mediaVersion'] = trackAPI['MEDIA_VERSION']

	if int(track['id'])<0:
		track['filesize'] = trackAPI['FILESIZE']
		track['album'] = {}
		track['album']['id'] = 0
		track['album']['title'] = trackAPI['ALB_TITLE']
		if 'ALB_PICTURE' in trackAPI:
			track['album']['pic'] = trackAPI['ALB_PICTURE']
		track['mainArtist'] = {}
		track['mainArtist']['id'] = 0
		track['mainArtist']['name'] = trackAPI['ART_NAME']
		track['artistArray'] = [trackAPI['ART_NAME']]
		track['date'] = {
			'day': 0,
			'month': 0,
			'year': 0
		}
		track['localTrack'] = True
		return track

	track['filesize'] = {}
	track['filesize']['default'] = int(trackAPI['FILESIZE']) if 'FILESIZE' in trackAPI else None
	track['filesize']['mp3_128'] = int(trackAPI['FILESIZE_MP3_128']) if 'FILESIZE_MP3_128' in trackAPI else None
	track['filesize']['mp3_320'] = int(trackAPI['FILESIZE_MP3_320']) if 'FILESIZE_MP3_320' in trackAPI else None
	track['filesize']['flac'] = int(trackAPI['FILESIZE_FLAC']) if 'FILESIZE_FLAC' in trackAPI else None
	track['filesize']['mp4_ra1'] = int(trackAPI['FILESIZE_MP4_RA1']) if 'FILESIZE_MP4_RA1' in trackAPI else None
	track['filesize']['mp4_ra2'] = int(trackAPI['FILESIZE_MP4_RA2']) if 'FILESIZE_MP4_RA2' in trackAPI else None
	track['filesize']['mp4_ra3'] = int(trackAPI['FILESIZE_MP4_RA3']) if 'FILESIZE_MP4_RA3' in trackAPI else None

	if 'DISK_NUMBER' in trackAPI:
		track['discNumber'] = trackAPI['DISK_NUMBER']
	if 'EXPLICIT_LYRICS' in trackAPI:
		track['explicit'] = trackAPI['EXPLICIT_LYRICS'] != "0"
	if 'COPYRIGHT' in trackAPI:
		track['copyright'] = trackAPI['COPYRIGHT']
	track['replayGain'] = "{0:.2f} dB".format((float(trackAPI['GAIN']) + 18.4) * -1)
	track['ISRC'] = trackAPI['ISRC']
	track['trackNumber'] = trackAPI['TRACK_NUMBER']
	if 'FALLBACK' in trackAPI:
		track['fallbackId'] = trackAPI['FALLBACK']['SNG_ID']
	else:
		track['fallbackId'] = 0
	track['contributors'] = trackAPI['SNG_CONTRIBUTORS']

	track['lyrics'] = {}
	if 'LYRICS_ID' in trackAPI:
		track['lyrics']['id'] = trackAPI['LYRICS_ID']
	if "LYRICS" in trackAPI:
		if "LYRICS_TEXT" in trackAPI["LYRICS"]:
			track['lyrics']['unsync'] = trackAPI["LYRICS"]["LYRICS_TEXT"]
		if "LYRICS_SYNC_JSON" in trackAPI["LYRICS"]:
			track['lyrics']['sync'] = ""
			for i in range(len(trackAPI["LYRICS"]["LYRICS_SYNC_JSON"])):
				if "lrc_timestamp" in trackAPI["LYRICS"]["LYRICS_SYNC_JSON"][i]:
					track['lyrics']['sync'] += trackAPI["LYRICS"]["LYRICS_SYNC_JSON"][i]["lrc_timestamp"] + trackAPI["LYRICS"]["LYRICS_SYNC_JSON"][i]["line"]+"\r\n"
				elif i+1 < len(trackAPI["LYRICS"]["LYRICS_SYNC_JSON"]):
					track['lyrics']['sync'] += trackAPI["LYRICS"]["LYRICS_SYNC_JSON"][i+1]["lrc_timestamp"] + trackAPI["LYRICS"]["LYRICS_SYNC_JSON"][i]["line"]+"\r\n"

	track['mainArtist'] = {}
	track['mainArtist']['id'] = trackAPI['ART_ID']
	track['mainArtist']['name'] = trackAPI['ART_NAME']
	if 'ART_PICTURE' in trackAPI:
		track['mainArtist']['pic'] = trackAPI['ART_PICTURE']

	if 'PHYSICAL_RELEASE_DATE' in trackAPI:
		track['date'] = {
			'day': trackAPI["PHYSICAL_RELEASE_DATE"][8:10],
			'month': trackAPI["PHYSICAL_RELEASE_DATE"][5:7],
			'year': trackAPI["PHYSICAL_RELEASE_DATE"][0:4]
		}

	track['album'] = {}
	track['album']['id'] = trackAPI['ALB_ID']
	track['album']['title'] = trackAPI['ALB_TITLE']
	if 'ALB_PICTURE' in trackAPI:
		track['album']['pic'] = trackAPI['ALB_PICTURE']

	try:
		albumAPI = dz.get_album(track['album']['id'])
		track['album']['artist'] = {
			'id': albumAPI['artist']['id'],
			'name': albumAPI['artist']['name'],
			'pic': albumAPI['artist']['picture_small'][46:-24]
		}
		track['album']['trackTotal'] = albumAPI['nb_tracks']
		track['album']['recordType'] = albumAPI['record_type']
		track['album']['barcode'] = albumAPI['upc'] if 'upc' in albumAPI else None
		track['album']['label'] = albumAPI['label'] if 'label' in albumAPI else None
		if not 'pic' in track['album']:
			track['album']['pic'] = albumAPI['cover_small'][43:-24]
		if 'release_date' in albumAPI:
			track['date'] = {
				'day': albumAPI["release_date"][8:10],
				'month': albumAPI["release_date"][5:7],
				'year': albumAPI["release_date"][0:4]
			}
		track['album']['genre'] = []
		if 'genres' in albumAPI and 'data' in albumAPI['genres'] and len(albumAPI['genres']['data'])>0:
			for genre in albumAPI['genres']['data']:
				track['album']['genre'].append(genre['name'])
	except APIError:
		albumAPI = dz.get_album_gw(track['album']['id'])
		track['album']['artist'] = {
			'id': albumAPI['ART_ID'],
			'name': albumAPI['ART_NAME']
		}
		track['album']['trackTotal'] = albumAPI['NUMBER_TRACK']
		track['album']['discTotal'] = albumAPI['NUMBER_DISK']
		track['album']['recordType'] = trackAPI['TYPE']
		track['album']['barcode'] = None
		track['album']['label'] = albumAPI['LABEL_NAME'] if 'LABEL_NAME' in albumAPI else None
		if not 'pic' in track['album']:
			track['album']['pic'] = albumAPI['ALB_PICTURE']
		if 'PHYSICAL_RELEASE_DATE' in albumAPI:
			track['date'] = {
				'day': albumAPI["PHYSICAL_RELEASE_DATE"][8:10],
				'month': albumAPI["PHYSICAL_RELEASE_DATE"][5:7],
				'year': albumAPI["PHYSICAL_RELEASE_DATE"][0:4]
			}
		track['album']['genre'] = []

	trackAPI2 = dz.get_track(track['id'])
	track['bpm'] = trackAPI2['bpm']
	if not 'replayGain' in track:
		track['replayGain'] = "{0:.2f} dB".format((float(trackAPI2['gain']) + 18.4) * -1)
	if not 'explicit' in track:
		track['explicit'] = trackAPI2['explicit_lyrics']
	track['artist'] = {}
	track['artists'] = []
	for artist in trackAPI2['contributors']:
		track['artists'].append(artist['name'])
		if not artist['role'] in track['artist']:
			track['artist'][artist['role']] = []
		track['artist'][artist['role']].append(artist['name'])

	if not 'discTotal' in track['album']:
		albumAPI2 = dz.get_album_gw(track['album']['id'])
		track['album']['discTotal'] = albumAPI2['NUMBER_DISK']
	return track

def downloadTrack(id, bitrate):
	# Get the metadata
	track = getTrackData(id)

	# Get the selected bitrate
	bitrateFound = False;
	if int(bitrate) == 9:
		track['selectedFormat'] = 9
		track['selectedFilesize'] = track['filesize']['flac']
		if track['filesize']['flac'] > 0:
			bitrateFound = True
		else:
			bitrateFound = False
			bitrate = 3
	if int(bitrate) == 3:
		track['selectedFormat'] = 3
		track['selectedFilesize'] = track['filesize']['mp3_320']
		if track['filesize']['mp3_320'] > 0:
			bitrateFound = True
		else:
			bitrateFound = False
			bitrate = 1
	if int(bitrate) == 1:
		track['selectedFormat'] = 3
		track['selectedFilesize'] = track['filesize']['mp3_320']
		if track['filesize']['mp3_320'] > 0:
			bitrateFound = True
		else:
			bitrateFound = False
	if not bitrateFound:
		track['selectedFormat'] = 8
		track['selectedFilesize'] = track['filesize']['default']
	track['album']['bitrate'] = track['selectedFormat']

	# Create the filename
	filename = "{artist} - {title}".format(title=track['title'], artist=track['mainArtist']['name'])+extensions[track['selectedFormat']]
	print(filename)

	track['downloadUrl'] = dz.get_track_stream_url(track['id'], track['MD5'], track['mediaVersion'], track['selectedFormat'])
	with open(filename, 'wb') as stream:
		dz.stream_track(track['id'], track['downloadUrl'], stream)
	if track['selectedFormat'] in [3,1,8]:
		tagID3(filename, track)
	elif track['selectedFormat'] == 9:
		tagFLAC(filename, track)
