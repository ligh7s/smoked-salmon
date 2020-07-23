# Changelog

Made a new file because there have been lots of changes recently.
   
# Changes 23/07/2020

## Multi tracker support
adds options DEFAULT_TRACKER and TRACKER_LIST (have a gander at config.py.txt example)  
--tracker or -t option for up command.   
Also allows uploading to multiple trackers with one command.  
So far only supports RED and OPS but groundwork is there for other gazelle sites at least.  


## Requests checkers
Adde the option to input a request id to be filled as you upload. (-r)  
The script now searches requests as you upload and offers a choice to fill one of the requests found as you upload. (can be disabled with CHECK_REQUESTS=False)  
Added ALWAYS_ASK_FOR_REQUEST_FILL option which if it is set to True the script will prompt you for a request to fill even if it doesn't find any itself.  

## Added recent upload dupe check
The script now searches for recent uploads similar to the release being uploaded in the site log.  
This is useful for special chars on recent content on RED or anything not yet showing up in the regular search.  
This function might be a little slow. It can be disabled with CHECK_RECENT_UPLOADS=False  

## Added option USE_UPC_AS_CATNO
The script now uses the upc as the catalogue number on site if a catalogue number is not found.  
This function will also append the UPC to whatever catno is found.  
This can be disabled with USE_UPC_AS_CATNO=False  

## Spectrals afer upload option. (-a)
This option will tell the script to only generate spectrals after the upload is complete.   
It is advised that you only use this if you are in a hurry to get the torrent uploaded.  
It important that you still always check your spectrals!
This feature then edits the existing torrent to add the spectrals to the description (and make a report if needed).


## checkspecs
Added command to check spectrals for a torrent on site.  
This is a standalone command that can check and add spectrals to the description of an already uploaded torrent. This requires you to have the files locally.
(see checkspecs -h for more info)  

# Other Changes 22/07/2020:
Use API key for upload on RED (full support still pending API coverage)  
Change the way torrent group id is picked on site.  
Use library for rate limiting  
Add library for rate limiting to requirements.txt  
Added choice to test 24 bit flac for upconverts on upload.  


