
# THWHelferboard
Small webapp to display a organism

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Total downloads](https://img.shields.io/github/downloads/nhet/THWHelferboard/total.svg)](https://github.com/nhet/THWHelferboard/releases/)
[![GitHub release](https://img.shields.io/github/release/nhet/THWHelferboard.svg)](https://github.com/nhet/THWHelferboard/releases/)
[![GitHub forks](https://img.shields.io/github/forks/nhet/THWHelferboard.svg?style=social&label=Fork&maxAge=2592000)](https://github.com/nhet/THWHelferboard/forks/)
[![GitHub stars](https://img.shields.io/github/stars/nhet/THWHelferboard.svg?style=social&label=Star&maxAge=2592000)](https://github.com/nhet/THWHelferboard/stargazers/)

## Description

THWHelferboard is a web-based application that provides an organism information display. It consists of a Python backend and a HTML/JavaScript frontend.

This work is licensed under **GNU AGPLv3**. See [LICENSE](./LICENSE) for more information.

## Features
 - Configure 
   - Groups
     - Name
     - WYSIWYG - Description
     - Images for carousel slider
   - Functions
     - Description
     - Short Description
     - Legend description
     - Logo as SVG
   - Helpers
     - Name
     - Photo
     - Group
     - Main function
     - Secondary functions
- Two step incognito mode
- Different import- and export functions


## 📦 Install
### Requirements
* Python >= 3.11
### Direct start on Docker with images

Download the Docker image for ARM64 or AMD64 for your platform from the [release](https://github.com/nhet/THWHelferboard/releases/) page.

### Install from source (latest features, recommended for development)

```bash
git clone https://github.com/nhet/THWHelferboard.git
cd THWHelferboard/backend
```

### 🚀 Quick start
#### Local environment
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

#### Build and deploy docker image:
```bash
docker build -t helferboard-backend .
docker run -d -p 8080:80 --name helferboard-app -v helferboard-db:/app/db -v helferboard-uploads:/app/app/static/uploads -e TMP=/app/tmp -e TMPDIR=/app/tmp --tmpfs /app/tmp:rw,size=30m helferboard-backend
```

### Open in browser
- Admin page: `http://<IP>:<PORT>/admin`
- Public page: `http://<IP>:<PORT>/`

### Version Information
The current version is displayed on the admin page at `/admin`.