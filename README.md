# Instagram Downloader
Script to bulk download images from instagram accoutns

# Getting Started
1. Login to instagram.
2. Copy the content of your cookie into the login_cookie file (remove .sample at the end)
    
    `To get the content of your cookie, open the developer console (f12) go to the network tab, if it is empty, reload the page with the network tab open. Then click the row that has the name of the account whose pictures you want to download in it. 
    A new window should open on the side. There you can see the "Response Headers" and further down the "Request Headers". In the "Request Headers" section should be the cookie, starting with "ig_did=". Completely copy the cookie into your login_cookie file.`
3. call `python3 ig_download <site-url> <(optional) download path>`