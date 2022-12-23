from pathlib import Path
import requests
import json
import sys
from parsel import Selector


headers = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Host": "www.instagram.com",
    "Referer": "https://www.instagram.com/lisainjapan/?hl=en",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:108.0) Gecko/20100101 Firefox/108.0",
}


def download_image(image: dict, download_folder: Path, session: requests.Session):
    node = image.get("node", headers=headers)
    if node.get("is_video"):
        return
    image_url = node.get("display_url")
    image_id = node.get("id")
    image_caption = (
        node.get("edge_media_to_caption", {}).get("edges", [{}])[0].get("node")
    )
    if image_url:
        image = session.get(image_url, headers=headers)
        with open(download_folder / f"{image_id}.jpg", "wb") as handler:
            handler.write(image)
        with open(download_folder / f"{image_id}.txt", "w") as out:
            out.write(image_caption)


def get_images_from_api(
    username: str, download_folder, session: requests.Session
) -> list:
    api_path = (
        f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    )
    profile_data = session.get(api_path, headers=headers).json()
    media = profile_data.get("edge_owner_to_timeline_media")
    image_count = media.get("count")
    if image_count <= 0:
        print("[!] This profile doesn't seem to have any images. Exiting")
        sys.exit()
    images = media.get("edges")
    for image in images:
        download_image(image, download_folder, session)
    has_next_page = media.get("page_info", {}).get("has_next_page")


def extract_user_from_url(url: str):
    return url.split("/")[3]


if __name__ == "__main__":
    url = sys.argv[1]
    if len(sys.argv) > 2:
        path = Path(sys.argv[2])
    else:
        path = Path()
    session = requests.Session()
    base_data = session.get(url, headers=headers)
    username = extract_user_from_url(url)
    download_folder = path / username
    download_folder.mkdir(exist_ok=True, parents=True)
    print(f"Created folder: {download_folder}")
    get_images_from_api(username, download_folder, session)
