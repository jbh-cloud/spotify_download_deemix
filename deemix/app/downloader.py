#!/usr/bin/env python3
from deemix.api.deezer import APIError, USER_AGENT_HEADER
from deemix.utils.taggers import tagID3, tagFLAC
from deemix.utils.pathtemplates import generateFilename, generateFilepath, settingsRegexAlbum, settingsRegexArtist
import os.path
from os import makedirs, remove
from requests import get
from requests.exceptions import HTTPError
from tempfile import gettempdir
from concurrent.futures import ThreadPoolExecutor

TEMPDIR = os.path.join(gettempdir(), 'deezloader-imgs')
if not os.path.isdir(TEMPDIR):
	makedirs(TEMPDIR)

extensions = {
	9: '.flac',
	3: '.mp3',
	1: '.mp3',
	8: '.mp3',
	15: '.mp4',
	14: '.mp4',
	13: '.mp4'
}

def downloadImage(url, path):
	if not os.path.isfile(path):
		with open(path, 'wb') as f:
			try:
				f.write(get(url, headers={'User-Agent': USER_AGENT_HEADER}).content)
				return path
			except HTTPError:
				print("Couldn't download Image")
		remove(path)
		return None
	else:
		return path

def formatDate(date, template):
	if 'YYYY' in template:
		template = template.replace('YYYY', str(date['year']))
	if 'YY' in template:
		template = template.replace('YY', str(date['year']))
	if 'Y' in template:
		template = template.replace('Y', str(date['year']))
	if 'MM' in template:
		template = template.replace('MM', str(date['month']))
	if 'M' in template:
		template = template.replace('M', str(date['month']))
	if 'DD' in template:
		template = template.replace('DD', str(date['day']))
	if 'D' in template:
		template = template.replace('D', str(date['day']))
	return template


def getPreferredBitrate(filesize, bitrate, fallback=True):
	if not fallback:
		formats = {9: 'flac', 3: 'mp3_320', 1: 'mp3_128', 15: '360_hq', 14: '360_mq', 13: '360_lq'}
		if filesize[formats[int(bitrate)]] > 0:
			return (int(bitrate), filesize[formats[int(bitrate)]])
		else:
			return (-100, 0)
	if int(bitrate) in [13,14,15]:
		formats = {'360_hq': 15, '360_mq': 14, '360_lq': 13}
		selectedFormat = -200
		selectedFilesize = 0
		for format, formatNum in formats.items():
			if formatNum <= int(bitrate) and filesize[format] > 0:
				selectedFormat = formatNum
				selectedFilesize = filesize[format]
				break
	else:
		formats = {'flac': 9, 'mp3_320': 3, 'mp3_128': 1}
		selectedFormat = 8
		selectedFilesize = filesize['default']
		for format, formatNum in formats.items():
			if formatNum <= int(bitrate) and filesize[format] > 0:
				selectedFormat = formatNum
				selectedFilesize = filesize[format]
				break
	return (selectedFormat, selectedFilesize)

def convertMetadata2Deezer(dz, artist, track, album):
	artist = artist.replace("–","-").replace("’", "'")
	track = track.replace("–","-").replace("’", "'")
	album = album.replace("–","-").replace("’", "'")

	resp = dz.search(f'artist:"{artist}" track:"{track}" album:"{album}"', "track", 1)
	if len(resp['data'])>0:
		return resp['data'][0]['id']
	resp = dz.search(f'artist:"{artist}" track:"{track}"', "track", 1)
	if len(resp['data'])>0:
		return resp['data'][0]['id']
	if "(" in track and ")" in track and track.find("(") < track.find(")"):
		resp = dz.search(f'artist:"{artist}" track:"{track[:track.find("(")]}"', "track", 1)
		if len(resp['data'])>0:
			return resp['data'][0]['id']
	elif " - " in track:
		resp = dz.search(f'artist:"{artist}" track:"{track[:track.find(" - ")]}"', "track", 1)
		if len(resp['data'])>0:
			return resp['data'][0]['id']
	else:
		return 0
	return 0

def parseEssentialTrackData(track, trackAPI):
	track['id'] = trackAPI['SNG_ID']
	track['duration'] = trackAPI['DURATION']
	track['MD5'] = trackAPI['MD5_ORIGIN']
	track['mediaVersion'] = trackAPI['MEDIA_VERSION']
	if 'FALLBACK' in trackAPI:
		track['fallbackId'] = trackAPI['FALLBACK']['SNG_ID']
	else:
		track['fallbackId'] = 0
	track['filesize'] = {}
	track['filesize']['default'] = int(trackAPI['FILESIZE']) if 'FILESIZE' in trackAPI else 0
	track['filesize']['mp3_128'] = int(trackAPI['FILESIZE_MP3_128']) if 'FILESIZE_MP3_128' in trackAPI else 0
	track['filesize']['mp3_320'] = int(trackAPI['FILESIZE_MP3_320']) if 'FILESIZE_MP3_320' in trackAPI else 0
	track['filesize']['flac'] = int(trackAPI['FILESIZE_FLAC']) if 'FILESIZE_FLAC' in trackAPI else 0
	track['filesize']['360_lq'] = int(trackAPI['FILESIZE_MP4_RA1']) if 'FILESIZE_MP4_RA1' in trackAPI else 0
	track['filesize']['360_mq'] = int(trackAPI['FILESIZE_MP4_RA2']) if 'FILESIZE_MP4_RA2' in trackAPI else 0
	track['filesize']['360_hq'] = int(trackAPI['FILESIZE_MP4_RA3']) if 'FILESIZE_MP4_RA3' in trackAPI else 0

	return track

def getTrackData(dz, trackAPI_gw, trackAPI = None, albumAPI_gw = None, albumAPI = None):
	if not 'MD5_ORIGIN' in trackAPI_gw:
		trackAPI_gw['MD5_ORIGIN'] = dz.get_track_md5(trackAPI_gw['SNG_ID'])

	track = {}
	track['title'] = trackAPI_gw['SNG_TITLE']
	if 'VERSION' in trackAPI_gw and trackAPI_gw['VERSION']:
		track['title'] += " " + trackAPI_gw['VERSION']

	track = parseEssentialTrackData(track, trackAPI_gw)

	if int(track['id']) < 0:
		track['filesize'] = trackAPI_gw['FILESIZE']
		track['album'] = {}
		track['album']['id'] = 0
		track['album']['title'] = trackAPI_gw['ALB_TITLE']
		if 'ALB_PICTURE' in trackAPI_gw:
			track['album']['pic'] = trackAPI_gw['ALB_PICTURE']
		track['mainArtist'] = {}
		track['mainArtist']['id'] = 0
		track['mainArtist']['name'] = trackAPI_gw['ART_NAME']
		track['artists'] = [trackAPI_gw['ART_NAME']]
		track['aritst'] = {
			'Main': [trackAPI_gw['ART_NAME']]
		}
		track['date'] = {
			'day': 0,
			'month': 0,
			'year': 0
		}
		track['localTrack'] = True
		return track

	if 'DISK_NUMBER' in trackAPI_gw:
		track['discNumber'] = trackAPI_gw['DISK_NUMBER']
	if 'EXPLICIT_LYRICS' in trackAPI_gw:
		track['explicit'] = trackAPI_gw['EXPLICIT_LYRICS'] != "0"
	if 'COPYRIGHT' in trackAPI_gw:
		track['copyright'] = trackAPI_gw['COPYRIGHT']
	track['replayGain'] = "{0:.2f} dB".format((float(trackAPI_gw['GAIN']) + 18.4) * -1) if 'GAIN' in trackAPI_gw else None
	track['ISRC'] = trackAPI_gw['ISRC']
	track['trackNumber'] = trackAPI_gw['TRACK_NUMBER']
	track['contributors'] = trackAPI_gw['SNG_CONTRIBUTORS']
	if 'POSITION' in trackAPI_gw:
		track['position'] = trackAPI_gw['POSITION']

	track['lyrics'] = {}
	if 'LYRICS_ID' in trackAPI_gw:
		track['lyrics']['id'] = trackAPI_gw['LYRICS_ID']
	if not "LYRICS" in trackAPI_gw and int(track['lyrics']['id']) != 0:
		trackAPI_gw["LYRICS"] = dz.get_lyrics_gw(track['id'])
	if int(track['lyrics']['id']) != 0:
		if "LYRICS_TEXT" in trackAPI_gw["LYRICS"]:
			track['lyrics']['unsync'] = trackAPI_gw["LYRICS"]["LYRICS_TEXT"]
		if "LYRICS_SYNC_JSON" in trackAPI_gw["LYRICS"]:
			track['lyrics']['sync'] = ""
			for i in range(len(trackAPI_gw["LYRICS"]["LYRICS_SYNC_JSON"])):
				if "lrc_timestamp" in trackAPI_gw["LYRICS"]["LYRICS_SYNC_JSON"][i]:
					track['lyrics']['sync'] += trackAPI_gw["LYRICS"]["LYRICS_SYNC_JSON"][i]["lrc_timestamp"] + \
											   trackAPI_gw["LYRICS"]["LYRICS_SYNC_JSON"][i]["line"] + "\r\n"
				elif i + 1 < len(trackAPI_gw["LYRICS"]["LYRICS_SYNC_JSON"]):
					track['lyrics']['sync'] += trackAPI_gw["LYRICS"]["LYRICS_SYNC_JSON"][i + 1]["lrc_timestamp"] + \
											   trackAPI_gw["LYRICS"]["LYRICS_SYNC_JSON"][i]["line"] + "\r\n"

	track['mainArtist'] = {}
	track['mainArtist']['id'] = trackAPI_gw['ART_ID']
	track['mainArtist']['name'] = trackAPI_gw['ART_NAME']
	if 'ART_PICTURE' in trackAPI_gw:
		track['mainArtist']['pic'] = trackAPI_gw['ART_PICTURE']

	if 'PHYSICAL_RELEASE_DATE' in trackAPI_gw:
		track['date'] = {
			'day': trackAPI_gw["PHYSICAL_RELEASE_DATE"][8:10],
			'month': trackAPI_gw["PHYSICAL_RELEASE_DATE"][5:7],
			'year': trackAPI_gw["PHYSICAL_RELEASE_DATE"][0:4]
		}

	track['album'] = {}
	track['album']['id'] = trackAPI_gw['ALB_ID']
	track['album']['title'] = trackAPI_gw['ALB_TITLE']
	if 'ALB_PICTURE' in trackAPI_gw:
		track['album']['pic'] = trackAPI_gw['ALB_PICTURE']

	try:
		if not albumAPI:
			albumAPI = dz.get_album(track['album']['id'])
		track['album']['mainArtist'] = {
			'id': albumAPI['artist']['id'],
			'name': albumAPI['artist']['name'],
			'pic': albumAPI['artist']['picture_small'][albumAPI['artist']['picture_small'].find('artist/')+7:-24]
		}
		track['album']['artist'] = {}
		track['album']['artists'] = []
		for artist in albumAPI['contributors']:
			if artist['id'] != 5080:
				track['album']['artists'].append(artist['name'])
				if not artist['role'] in track['album']['artist']:
					track['album']['artist'][artist['role']] = []
				track['album']['artist'][artist['role']].append(artist['name'])
		track['album']['trackTotal'] = albumAPI['nb_tracks']
		track['album']['recordType'] = albumAPI['record_type']
		track['album']['barcode'] = albumAPI['upc'] if 'upc' in albumAPI else "Unknown"
		track['album']['label'] = albumAPI['label'] if 'label' in albumAPI else "Unknown"
		if not 'pic' in track['album']:
			track['album']['pic'] = albumAPI['cover_small'][albumAPI['cover_small'].find('cover/')+6:-24]
		if 'release_date' in albumAPI:
			track['album']['date'] = {
				'day': albumAPI["release_date"][8:10],
				'month': albumAPI["release_date"][5:7],
				'year': albumAPI["release_date"][0:4]
			}
		track['album']['discTotal'] = albumAPI['nb_disk'] if 'nb_disk' in albumAPI else None
		track['copyright'] = albumAPI['copyright'] if 'copyright' in albumAPI else None
		track['album']['genre'] = []
		if 'genres' in albumAPI and 'data' in albumAPI['genres'] and len(albumAPI['genres']['data']) > 0:
			for genre in albumAPI['genres']['data']:
				track['album']['genre'].append(genre['name'])
	except APIError:
		if not albumAPI_gw:
			albumAPI_gw = dz.get_album_gw(track['album']['id'])
		track['album']['mainArtist'] = {
			'id': albumAPI_gw['ART_ID'],
			'name': albumAPI_gw['ART_NAME']
		}
		artistAPI = dz.get_artist(track['album']['mainArtist']['id'])
		track['album']['artists'] = albumAPI_gw['ART_NAME']
		track['album']['mainArtist']['pic'] = artistAPI['picture_small'][artistAPI['picture_small'].find('artist/')+7:-24]
		track['album']['trackTotal'] = albumAPI_gw['NUMBER_TRACK']
		track['album']['discTotal'] = albumAPI_gw['NUMBER_DISK']
		track['album']['recordType'] = "Album"
		track['album']['barcode'] = "Unknown"
		track['album']['label'] = albumAPI_gw['LABEL_NAME'] if 'LABEL_NAME' in albumAPI_gw else "Unknown"
		if not 'pic' in track['album']:
			track['album']['pic'] = albumAPI_gw['ALB_PICTURE']
		if 'PHYSICAL_RELEASE_DATE' in albumAPI_gw:
			track['album']['date'] = {
				'day': albumAPI_gw["PHYSICAL_RELEASE_DATE"][8:10],
				'month': albumAPI_gw["PHYSICAL_RELEASE_DATE"][5:7],
				'year': albumAPI_gw["PHYSICAL_RELEASE_DATE"][0:4]
			}
		track['album']['genre'] = []

	if 'date' in track['album']:
		track['date'] = track['album']['date']

	if not trackAPI:
		trackAPI = dz.get_track(track['id'])
	track['bpm'] = trackAPI['bpm']
	if not 'replayGain' in track:
		track['replayGain'] = "{0:.2f} dB".format((float(trackAPI['gain']) + 18.4) * -1) if 'gain' in trackAPI else ""
	if not 'explicit' in track:
		track['explicit'] = trackAPI['explicit_lyrics']
	if not 'discNumber' in track:
		track['discNumber'] = trackAPI['disk_number']
	track['artist'] = {}
	track['artists'] = []
	for artist in trackAPI['contributors']:
		if artist['id'] != 5080:
			track['artists'].append(artist['name'])
			if not artist['role'] in track['artist']:
				track['artist'][artist['role']] = []
			track['artist'][artist['role']].append(artist['name'])

	if not 'discTotal' in track['album'] or not track['album']['discTotal']:
		if not albumAPI_gw:
			albumAPI_gw = dz.get_album_gw(track['album']['id'])
		track['album']['discTotal'] = albumAPI_gw['NUMBER_DISK']
	if not 'copyright' in track or not track['copyright']:
		if not albumAPI_gw:
			albumAPI_gw = dz.get_album_gw(track['album']['id'])
		track['copyright'] = albumAPI_gw['COPYRIGHT']

	# Fix incorrect day month when detectable
	if int(track['date']['month']) > 12:
		monthTemp = track['date']['month']
		track['date']['month'] = track['date']['day']
		track['date']['day'] = monthTemp
	if int(track['album']['date']['month']) > 12:
		monthTemp = track['album']['date']['month']
		track['album']['date']['month'] = track['album']['date']['day']
		track['album']['date']['day'] = monthTemp

	# Remove featuring from the title
	track['title_clean'] = track['title']
	if "(feat." in track['title_clean'].lower():
		pos = track['title_clean'].lower().find("(feat.")
		tempTrack = track['title_clean'][:pos]
		if ")" in track['title_clean']:
			tempTrack += track['title_clean'][track['title_clean'].find(")",pos+1)+1:]
		track['title_clean'] = tempTrack.strip()

	# Create artists strings
	track['mainArtistsString'] = ""
	if 'Main' in track['artist']:
		tot = len(track['artist']['Main'])
		for i, art in enumerate(track['artist']['Main']):
			track['mainArtistsString'] += art
			if tot != i+1:
				if tot-1 == i+1:
					track['mainArtistsString'] += " & "
				else:
					track['mainArtistsString'] += ", "
	else:
		track['mainArtistsString'] = track['mainArtist']['name']
	if 'Featured' in track['artist']:
		tot = len(track['artist']['Featured'])
		track['featArtistsString'] = "feat. "
		for i, art in enumerate(track['artist']['Featured']):
			track['featArtistsString'] += art
			if tot != i+1:
				if tot-1 == i+1:
					track['featArtistsString'] += " & "
				else:
					track['featArtistsString'] += ", "

	# Create title with feat
	if "(feat." in track['title'].lower():
		track['title_feat'] = track['title']
	elif 'Featured' in track['artist']:
		track['title_feat'] = track['title']+" ({})".format(track['featArtistsString'])
	else:
		track['title_feat'] = track['title']

	return track

def downloadTrackObj(dz, trackAPI, settings, overwriteBitrate=False, extraTrack=None):
	result = {}
	# Get the metadata
	if extraTrack:
		track = extraTrack
	else:
		track = getTrackData(dz,
			trackAPI_gw = trackAPI,
			trackAPI =  trackAPI['_EXTRA_TRACK'] if '_EXTRA_TRACK' in trackAPI else None,
			albumAPI = trackAPI['_EXTRA_ALBUM'] if '_EXTRA_ALBUM' in trackAPI else None
		)
	print('Downloading: {} - {}'.format(track['mainArtist']['name'], track['title']))
	if track['MD5'] == '':
		if track['fallbackId'] != 0:
			print("Track not yet encoded, using fallback id")
			trackNew = dz.get_track_gw(track['fallbackId'])
			if not 'MD5_ORIGIN' in trackNew:
				trackNew['MD5_ORIGIN'] = dz.get_track_md5(trackNew['SNG_ID'])
			track = parseEssentialTrackData(track, trackNew)
			return downloadTrackObj(dz, trackAPI, settings, extraTrack=track)
		elif not 'searched' in track and settings['fallbackSearch']:
			print("Track not yet encoded, searching for alternative")
			searchedId = convertMetadata2Deezer(dz, track['mainArtist']['name'], track['title'], track['album']['title'])
			if searchedId != 0:
				trackNew = dz.get_track_gw(searchedId)
				if not 'MD5_ORIGIN' in trackNew:
					trackNew['MD5_ORIGIN'] = dz.get_track_md5(trackNew['SNG_ID'])
				track = parseEssentialTrackData(track, trackNew)
				track['searched'] = True
				return downloadTrackObj(dz, trackAPI, settings, extraTrack=track)
			else:
				print("ERROR: Track not yet encoded and no alternative found!")
				result['error'] = {
					'message': "Track not yet encoded and no alternative found!",
					'data': track
				}
				return result
		else:
			print("ERROR: Track not yet encoded!")
			result['error'] = {
				'message': "Track not yet encoded!",
				'data': track
			}
			return result

	# Get the selected bitrate
	bitrate = overwriteBitrate if overwriteBitrate else settings['maxBitrate']
	(format, filesize) = getPreferredBitrate(track['filesize'], bitrate, settings['fallbackBitrate'])
	if format == -100:
		print("ERROR: Track not found at desired bitrate. Enable fallback to lower bitrates to fix this issue.")
		result['error'] = {
			'message': "Track not found at desired bitrate.",
			'data': track
		}
		return result
	elif format == -200:
		print("ERROR: This track is not available in 360 Reality Audio format. Please select another format.")
		result['error'] = {
			'message': "Track is not available in Reality Audio 360.",
			'data': track
		}
		return result
	track['selectedFormat'] = format
	track['selectedFilesize'] = filesize
	track['album']['bitrate'] = format
	track['album']['picUrl'] = "https://e-cdns-images.dzcdn.net/images/cover/{}/{}x{}-000000-80-0-0.{}".format(track['album']['pic'], settings['embeddedArtworkSize'], settings['embeddedArtworkSize'], 'png' if settings['PNGcovers'] else 'jpg')
	track['dateString'] = formatDate(track['date'], settings['dateFormat'])
	track['album']['dateString'] = formatDate(track['album']['date'], settings['dateFormat'])

	# Generate filename and filepath from metadata
	filename = generateFilename(track, trackAPI, settings)
	(filepath, artistPath, coverPath, extrasPath) = generateFilepath(track, trackAPI, settings)

	# Download and cache coverart
	track['album']['picPath'] = os.path.join(TEMPDIR, f"alb{track['album']['id']}_{settings['embeddedArtworkSize']}.{'png' if settings['PNGcovers'] else 'jpg'}")
	track['album']['picPath'] = downloadImage(track['album']['picUrl'], track['album']['picPath'])

	makedirs(filepath, exist_ok=True)
	writepath = os.path.join(filepath, filename + extensions[track['selectedFormat']])

	# Save lyrics in lrc file
	if settings['syncedLyrics'] and 'sync' in track['lyrics']:
		with open(os.path.join(filepath, filename + '.lrc'), 'w') as f:
			f.write(track['lyrics']['sync'])

	# Save local album art
	if coverPath:
		result['albumURL'] = track['album']['picUrl'].replace(f"{settings['embeddedArtworkSize']}x{settings['embeddedArtworkSize']}", f"{settings['localArtworkSize']}x{settings['localArtworkSize']}")
		result['albumPath'] = os.path.join(coverPath, f"{settingsRegexAlbum(settings['coverImageTemplate'], track['album'], settings)}.{'png' if settings['PNGcovers'] else 'jpg'}")

	# Save artist art
	if artistPath:
		result['artistURL'] = "https://e-cdns-images.dzcdn.net/images/artist/{}/{}x{}-000000-80-0-0.{}".format(track['album']['artist']['pic'], settings['localArtworkSize'], settings['localArtworkSize'], 'png' if settings['PNGcovers'] else 'jpg')
		result['artistPath'] = os.path.join(artistPath, f"{settingsRegexArtist(settings['artistImageTemplate'], track['album']['artist'], settings)}.{'png' if settings['PNGcovers'] else 'jpg'}")

	# Data for m3u file
	if extrasPath:
		result['extrasPath'] = extrasPath
		result['playlistPosition'] = writepath[len(extrasPath):]

	# Generate artist tag if needed
	if settings['multitagSeparator'] != "default":
		if settings['multitagSeparator'] == "andFeat":
			track['artistsString'] = track['mainArtistsString']
			if 'featArtistsString' in track:
				track['artistsString'] += " "+track['featArtistsString']
		else:
			track['artistsString'] = settings['multitagSeparator'].join(track['artists'])

	track['downloadUrl'] = dz.get_track_stream_url(track['id'], track['MD5'], track['mediaVersion'], track['selectedFormat'])
	try:
		with open(writepath, 'wb') as stream:
			dz.stream_track(track['id'], track['downloadUrl'], stream)
	except HTTPError:
		remove(writepath)
		if track['selectedFormat'] == 9 and settings['fallbackBitrate']:
			print("Track not available in flac, trying mp3")
			track['filesize']['flac'] = 0
			return downloadTrackObj(dz, trackAPI, settings, extraTrack=track)
		elif track['fallbackId'] != 0:
			print("Track not available, using fallback id")
			trackNew = dz.get_track_gw(track['fallbackId'])
			if not 'MD5_ORIGIN' in trackNew:
				trackNew['MD5_ORIGIN'] = dz.get_track_md5(trackNew['SNG_ID'])
			track = parseEssentialTrackData(track, trackNew)
			return downloadTrackObj(dz, trackAPI, settings, extraTrack=track)
		elif not 'searched' in track and settings['fallbackSearch']:
			print("Track not available, searching for alternative")
			searchedId = convertMetadata2Deezer(dz, track['mainArtist']['name'], track['title'], track['album']['title'])
			if searchedId != 0:
				trackNew = dz.get_track_gw(searchedId)
				if not 'MD5_ORIGIN' in trackNew:
					trackNew['MD5_ORIGIN'] = dz.get_track_md5(trackNew['SNG_ID'])
				track = parseEssentialTrackData(track, trackNew)
				track['searched'] = True
				return downloadTrackObj(dz, trackAPI, settings, extraTrack=track)
			else:
				print("ERROR: Track not available on deezer's servers and no alternative found!")
				result['error'] = {
					'message': "Track not available on deezer's servers and no alternative found!",
					'data': track
				}
				return result
		else:
			print("ERROR: Track not available on deezer's servers!")
			result['error'] = {
				'message': "Track not available on deezer's servers!",
				'data': track
			}
			return result
	if track['selectedFormat'] in [3, 1, 8]:
		tagID3(writepath, track, settings['tags'], settings['saveID3v1'], settings['useNullSeparator'])
	elif track['selectedFormat'] == 9:
		tagFLAC(writepath, track, settings['tags'])
	if 'searched' in track:
		result['searched'] = f'{track["mainArtist"]["name"]} - {track["title"]}'
	print("Done!")
	return result

def after_download(tracks, settings):
	extrasPath = None
	playlist = [None] * len(tracks)
	errors = ""
	searched = ""
	for index in range(len(tracks)):
		result = tracks[index].result()
		if 'error' in result:
			errors += f"{result['error']['data']['id']} | {result['error']['data']['mainArtist']['name']} - {result['error']['data']['title']} | {result['error']['message']}\r\n"
		if 'searched' in result:
			searched += result['searched']+"\r\n"
		if not extrasPath and 'extrasPath' in result:
			extrasPath = result['extrasPath']
		if settings['saveArtwork'] and result['albumPath']:
			downloadImage(result['albumURL'], result['albumPath'])
		if settings['saveArtworkArtist'] and result['artistPath']:
			downloadImage(result['artistURL'], result['artistPath'])
		if 'playlistPosition' in result:
			playlist[index] = result['playlistPosition']
		else:
			playlist[index] = ""
	if settings['logErrors'] and extrasPath and errors != "":
		with open(os.path.join(extrasPath, 'errors.txt'), 'w') as f:
			f.write(errors)
	if settings['logSearched'] and extrasPath and searched != "":
		with open(os.path.join(extrasPath, 'searched.txt'), 'w') as f:
			f.write(searched)
	if settings['createM3U8File'] and extrasPath:
		with open(os.path.join(extrasPath, 'playlist.m3u8'), 'w') as f:
			for line in playlist:
				f.write(line+"\n")
	return extrasPath

def after_download_single(track, settings):
	if settings['logSearched'] and 'extrasPath' in result and 'searched' in result:
		with open(os.path.join(result['extrasPath'], 'searched.txt'), 'w+') as f:
			orig = f.read()
			if not result['searched'] in orig:
				if orig != "":
					orig += "\r\n"
				orig += result['searched']+"\r\n"
			f.write(orig)
	if 'extrasPath' in result:
		return result['extrasPath']
	else:
		return None

def download_track(dz, id, settings, overwriteBitrate=False):
	trackAPI = dz.get_track_gw(id)
	trackAPI['FILENAME_TEMPLATE'] = settings['tracknameTemplate']
	trackAPI['SINGLE_TRACK'] = True
	result = downloadTrackObj(dz, trackAPI, settings, overwriteBitrate)
	return after_download_single(result, settings)


def download_album(dz, id, settings, overwriteBitrate=False):
	albumAPI = dz.get_album(id)
	albumAPI_gw = dz.get_album_gw(id)
	albumAPI['nb_disk'] = albumAPI_gw['NUMBER_DISK']
	albumAPI['copyright'] = albumAPI_gw['COPYRIGHT']
	if albumAPI['nb_tracks'] == 1:
		trackAPI = dz.get_track_gw(albumAPI['tracks']['data'][0]['id'])
		trackAPI['_EXTRA_ALBUM'] = albumAPI
		trackAPI['FILENAME_TEMPLATE'] = settings['tracknameTemplate']
		trackAPI['SINGLE_TRACK'] = True
		result = downloadTrackObj(dz, trackAPI, settings, overwriteBitrate)
		return after_download_single(result, settings)
	else:
		tracksArray = dz.get_album_tracks_gw(id)
		playlist = [None] * len(tracksArray)
		with ThreadPoolExecutor(settings['queueConcurrency']) as executor:
			for pos, trackAPI in enumerate(tracksArray, start=1):
				trackAPI['_EXTRA_ALBUM'] = albumAPI
				trackAPI['POSITION'] = pos
				trackAPI['FILENAME_TEMPLATE'] = settings['albumTracknameTemplate']
				playlist[pos-1] = executor.submit(downloadTrackObj, dz, trackAPI, settings, overwriteBitrate)

		return after_download(playlist, settings)

def download_artist(dz, id, settings, overwriteBitrate=False):
	artistAPI = dz.get_artist_albums(id)
	for album in artistAPI['data']:
		print(f"Album: {album['title']}")
		download_album(dz, album['id'], settings, overwriteBitrate)

def download_playlist(dz, id, settings, overwriteBitrate=False):
	playlistAPI = dz.get_playlist(id)
	playlistTracksAPI = dz.get_playlist_tracks_gw(id)
	playlist = [None] * len(playlistTracksAPI)
	with ThreadPoolExecutor(settings['queueConcurrency']) as executor:
		for pos, trackAPI in enumerate(playlistTracksAPI, start=1):
			trackAPI['_EXTRA_PLAYLIST'] = playlistAPI
			trackAPI['POSITION'] = pos
			trackAPI['FILENAME_TEMPLATE'] = settings['playlistTracknameTemplate']
			playlist[pos-1] = executor.submit(downloadTrackObj, dz, trackAPI, settings, overwriteBitrate)
	return after_download(playlist, settings)
