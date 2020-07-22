CHANGELOG.md

New file because there have been lots of changes recently.

##Changes
Multi tracker support
	--tracker or -t option
	Upload to multiple trackers with one command

	
Use upc as cat# if no cat# is available and always put UPC with CAT # (Setting avalible to turn this off)
Always put UPC onsite in cat no box (unless set not to use it)

Allow you to input a request id as you upload. (-r)
Search requests as you upload.

Added recent upload dupe check (useful for special chars on recent content on RED)

Add spectrals afer upload option. (-a)

Add checkspecs command for torrents on site.

##Other changes:
Use API key for upload on RED (full support still pending API coverage)
Change the way torrent group id is picked on site.
Use library for rate limiting
Add library for rate limiting to requirements.txt
Scrape deezer cover internally not from public api deezer. (fixes cover fetch for new releases)

##Changes in plugin:
Allow queue to use different trackers
Persistant flag (-p) for queue dl and up. Otherwise stops when done.
Added Label search
