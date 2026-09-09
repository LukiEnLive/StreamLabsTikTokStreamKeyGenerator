# TikTok Live Stream Key Generator for OBS Studio Using Streamlabs API

## Description

This application is a simple tool that generates a TikTok Live Stream Key for OBS Studio using the Streamlabs API.

Streamlabs TikTok LIVE access is required.

## Features

* Generate TikTok Live Stream Key using Streamlabs API

## Requirements

* Streamlabs TikTok LIVE access. You can request access [here](https://tiktok.com/falcon/live_g/live_access_pc_apply/result/index.html?id=GL6399433079641606942&lang=en-US)
* TikTok account
* Streamlabs installed on your computer and you are logged in with your TikTok account in Streamlabs (optional)

## Download

Download the latest release from the [Releases](../../releases/latest) page.

## Usage

1. Run the application.
2. Click on the **Load from PC** button if you have Streamlabs installed on your computer and you are logged in with your TikTok account in Streamlabs. Otherwise, click on the **Login from Web** button.
3. Select stream title and category.
4. Click on the **Save Config** button to save the token, title and category.
5. Click on the **Go Live** button.

## Screenshots

![Screenshot](https://i.imgur.com/2PSgEQP.png)

## Output

The app will output:

* **Stream URL:** The URL needed to connect to the TikTok live stream.
* **Stream key for OBS Studio (or any other streaming app):** The stream key that you can use in OBS Studio to stream to TikTok.

## Credits

This project is based on the original work by [Loukious](https://github.com/Loukious/StreamLabsTikTokStreamKeyGenerator).

This fork is maintained and developed by [LukiEnLive](https://github.com/LukiEnLive).

## FAQ

### I'm getting a "You can't open the application..." error on macOS. What should I do?

I don't own a Mac so I can't test the app on macOS, but you can try the following:

1. Open Terminal.
2. Run the following command:

```bash
xattr -dr com.apple.quarantine /path/to/the/StreamLabsTikTokStreamKeyGenerator.app
```

Replace `/path/to/the/StreamLabsTikTokStreamKeyGenerator.app` with the path to the application.

3. Try to run the app again.

### I'm getting an error when I try to stream. What should I do?

1. First, make sure it's not an issue related to Streamlabs. Try going live using Streamlabs and see if you get the same error.
2. If it's not an issue related to Streamlabs, you can create an issue on GitHub with the error message and a screenshot of the error.

### Do I need to have 1k followers to get Streamlabs TikTok LIVE access?

No, you can request access even if you have less than 1k followers.
