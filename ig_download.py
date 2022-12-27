from pathlib import Path
import httpx
import sys
from parsel import Selector
import re
import urllib.parse
import json


class InstagramUser:
    headers = {
        "authority": "www.instagram.com",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "dnt": "1",
        "Connection": "keep-alive",
        "Host": "www.instagram.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:108.0) Gecko/20100101 Firefox/108.0",
    }
    profile_post_actions = ""
    user_id = ""
    last_cursor = ""
    pagination_url = "https://www.instagram.com/graphql/query/?query_hash=69cba40317214236af40e7efa697781d&variables={encoded_data}"

    def tagtize_caption(self, description: str) -> str:
        words = description.split()
        tags = list()
        for word in words:
            if word.startswith("#"):
                tags.append(word[1:])
        return ", ".join(tags)

    def download_image(self, image: dict):
        downloads = list()
        node = image.get("node")
        if node.get("is_video"):
            return
        image_url = node.get("display_url")
        images = node.get("edge_sidecar_to_children", {}).get("edges", {})
        image_id = node.get("id")
        if not images:
            downloads.append([image_url, image_id])
        else:
            for i, image_obj in enumerate(images):
                img = image_obj.get("node")
                downloads.append([img["display_url"], img["id"]])
        image_caption: str = (
            node.get("edge_media_to_caption", {}).get("edges", [{}])[0].get("node")
        ).get("text")
        image_caption_tagged = self.tagtize_caption(image_caption)
        for download in downloads:
            image_bytes = httpx.get(download[0]).content
            with open(self.download_folder / f"{download[1]}.jpg", "wb") as handler:
                handler.write(image_bytes)
            with open(self.download_folder / f"{download[1]}.txt", "wb") as out:
                out.write(image_caption_tagged.encode("utf-8"))
            with open(self.download_folder / f"{download[1]}_raw.txt", "wb") as out:
                out.write(image_caption.encode("utf-8"))
            self.image_count += 1

    def extract_csrf_data(self, response: httpx.Response, csrf_token: str):
        rows = response.text.splitlines()
        csrf_headers = {"x-ig-www-claim": "0", "csrf_token": csrf_token}
        for row in rows:
            if '__d("PolarisBDHeaderConfig"' in row:
                csrf_headers["x-asbd-id"] = re.match('.*;a="(\d+)"', row).group(1)
            if '__d("PolarisConfigConstants"' in row:
                csrf_headers["x-ig-app-id"] = re.match('.*;b="(\d+)"', row).group(1)
        return csrf_headers

    def extract_image_urls(self, user_data: dict):
        user = user_data.get("data", {}).get("user")
        media = user.get("edge_owner_to_timeline_media")
        image_count = media.get("count")
        if image_count <= 0:
            print("[!] This profile doesn't seem to have any images. Exiting")
            sys.exit()
        images = media.get("edges")
        if not self.user_id:
            self.user_id = user.get("id")
        self.has_next_page = media.get("page_info", {}).get("has_next_page")
        self.last_cursor = media.get("page_info", {}).get("end_cursor")
        return images

    def setup_user_context(self) -> list:
        api_path = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={self.username}"
        user_data = self.client.get(api_path, headers=self.headers).json()
        # print(dict(self.client.cookies))
        return self.extract_image_urls(user_data)

    def extract_user_from_url(self):
        return self.url.split("/")[3]

    def add_csrf_headers(self, base_selector):
        csrf_data_url = base_selector.xpath(
            "//link[contains(@href, 'rsrc.php/v3') and contains(@href, 'RHgDfKYaJaQ')]/@href"
        ).get()
        csrf_response = httpx.get(csrf_data_url)
        lazy_load = base_selector.xpath(
            "//script[contains(text(), 'csrf_token')]"
        ).get()
        csrf_token = re.match('.*csrf_token\\\\":\\\\"(\w+)', lazy_load).group(1)
        csrf_headers = self.extract_csrf_data(csrf_response, csrf_token)
        self.headers.update(csrf_headers)

    def follow_pagination(self):
        pagination_data = urllib.parse.quote(
            json.dumps({"id": self.user_id, "first": 12, "after": self.last_cursor})
        )
        next_page = self.pagination_url.format(encoded_data=pagination_data)
        user_data = self.client.get(next_page, headers=self.headers)
        user_data_json = user_data.json()
        return self.extract_image_urls(user_data_json)

    def download(self):
        base_data = self.client.get(self.url, headers=self.headers)
        base_selector = Selector(base_data.text)
        self.add_csrf_headers(base_selector)
        first_images = self.setup_user_context()
        for image in first_images:
            self.download_image(image)
        self.page += 1
        print(
            f"Downloaded images from page: {self.page}\nDownloaded images: {self.image_count}"
        )
        while self.has_next_page:
            images = self.follow_pagination()
            self.page += 1
            for image in images:
                self.download_image(image)
                print(
                    f"Downloaded images from page: {self.page}\nDownloaded images: {self.image_count}"
                )

    def setup_folder(self):
        if len(sys.argv) > 2:
            path = Path(sys.argv[2])
        else:
            path = Path("./downloads")
        self.download_folder = path / self.username
        self.download_folder.mkdir(exist_ok=True, parents=True)
        print(f"Created folder: {self.download_folder}")

    def set_login_cookies(self):
        with open("login_cookie", "r") as cookie_file:
            cookies_raw = cookie_file.read()
        cookie_data = dict()
        cookies = cookies_raw.split(";")
        cookie_data = {
            cookie.split("=")[0].strip(): cookie.split("=")[1].strip()
            for cookie in cookies
            if "=" in cookie
        }
        self.client.cookies.update(cookie_data)

    def __init__(self) -> None:
        self.page = 0  # only for debug output
        self.image_count = 0  # only for debug output
        self.url = sys.argv[1]
        if not self.url.endswith("/"):
            raise ValueError(
                "Url has to end with '/' otherwise instagram will deny the request"
            )
        self.username = self.extract_user_from_url()
        print(f"Starting download of images from user: {self.username}")
        self.client = httpx.Client()
        self.set_login_cookies()
        self.setup_folder()
        self.headers["Referer"] = f"https://www.instagram.com/{self.username}/?hl=en"


if __name__ == "__main__":
    user = InstagramUser()
    user.download()
