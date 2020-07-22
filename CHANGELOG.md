CHANGELOG.md

Made a new file because there have been lots of changes recently.
   
#Changes 22/07/2020
##Multi tracker support
    adds options DEFAULT_TRACKER and TRACKER_LIST (have a gander at config.py.txt example)
	--tracker or -t option for up command. 
	Also allows uploading to multiple trackers with one command.
    So far only supports RED and OPS but groundwork is there for other gazelle sites at least.


##Requests checkers
Allow you to input a request id to fill as you upload. (-r)
Searches requests as you upload
Added ALWAYS_ASK_FOR_REQUEST_FILL
If this is set to True the script will prompt you for a request to fill even if it doesn't find any.

##Added recent upload dupe check
This is useful for special chars on recent content on RED or anything not yet showing up in search.
This function might be a little slow.
It can be disabled with CHECK_RECENT_UPLOADS=False

##Added option (USE_UPC_AS_CATNO)	to use upc as the catelouge number on site. 
This option will also append the UPC to the catno field on site.

##Spectrals afer upload option. (-a)
This option will only generate spectrals after the upload is complete. 
It is advised that you only use this if you are in a hurry to get the torrent up.
It important that you still always check your spectrals!


##checkspecs
Added command to check spectrals for a torrent on site.
This is a standalone command that can check and add spectrals to the description of an already uploaded torrent.
(see checkspecs -h for more info)

#Other Changes 22/07/2020:
Use API key for upload on RED (full support still pending API coverage)
Change the way torrent group id is picked on site.
Use library for rate limiting
Add library for rate limiting to requirements.txt
Scrape deezer cover internally not from public api deezer. (fixes cover fetching for new releases)
Added choice to test 24 bit flac for upconverts on upload.


