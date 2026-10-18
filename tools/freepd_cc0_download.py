#!/usr/bin/env python3
"""Public-domain-only music transfer. No private DLM media or account secrets."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

UPSTREAM = "0lhi/FreePD"
PIN = "cf011c7016595833b550a88ff127f089188b25f8"
FILES = {
    "Scoring/Find Them.mp3": ("f73ffffba44e4ee953db0087cf74bcefd8500c14", 5729581, "investigation"),
    "Electronic/Chronos.mp3": ("2b9ab73f2a3de43274b54a8e90611bb7efefb54d", 4387205, "technical"),
    "Scoring/Driving Concern.mp3": ("3eda41be22cff3dcb1bb47ac0b7fd4b9c289f7a1", 8018584, "finance"),
    "Scoring/Slice of Life.mp3": ("b8c18376f775ef14c7dc56e7c819bc90fc4c67cb", 2817471, "human"),
    "Scoring/Final Step.mp3": ("293f82fc89ebce5b7f78d85723673a1ae22b4991", 3819216, "conclusion"),
}
LICENSE_GIT_SHA = "0e259d42c996742e9e3cba14c677129b2c1b6311"
ROOT = Path("out/freepd-cc0")
MAX = 12_000_000

def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def urls(path):
    encoded = quote(path, safe="/")
    return [
        "https://raw.githubusercontent.com/" + UPSTREAM + "/" + PIN + "/" + encoded,
        "https://cdn.jsdelivr.net/gh/" + UPSTREAM + "@" + PIN + "/" + encoded,
        "https://github.com/" + UPSTREAM + "/raw/" + PIN + "/" + encoded,
    ]

def download_checked(path, expected_sha, expected_size=None):
    failures=[]
    for uri in urls(path):
        for attempt in range(2):
            try:
                req=Request(uri, headers={"User-Agent":"WAP-CC0-Source-Archive/1.0",
                                         "Accept":"application/octet-stream"})
                with urlopen(req, timeout=25) as res:
                    data=res.read(MAX+1)
                if len(data)>MAX:
                    raise ValueError("oversize")
                if expected_size is not None and len(data)!=expected_size:
                    raise ValueError("size mismatch")
                if git_blob_sha(data)!=expected_sha:
                    raise ValueError("Git blob SHA mismatch")
                return data,uri
            except Exception as e:
                failures.append(uri.split("/")[2]+":"+type(e).__name__+":"+str(e)[:110])
                if attempt==0:
                    time.sleep(1)
    raise RuntimeError("All immutable-source mirrors failed: "+" | ".join(failures))

def duration_seconds(file):
    p=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                     "-of","default=noprint_wrappers=1:nokey=1",str(file)],
                     capture_output=True,text=True,timeout=30,check=True)
    return float(p.stdout.strip())

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    license_bytes,license_source=download_checked("LICENSE",LICENSE_GIT_SHA)
    doc=license_bytes.decode("utf-8")
    if not all(s in doc for s in ["CC0 1.0 Universal","Creative Commons","Waiver"]):
        raise RuntimeError("License text does not establish upstream CC0 declaration")
    (ROOT/"LICENSE").write_bytes(license_bytes)
    tracks=[]
    for path,(expected_sha,size,mood) in FILES.items():
        data,uri=download_checked(path,expected_sha,size)
        filename=path.replace("/","__")
        target=ROOT/filename
        target.write_bytes(data)
        dur=duration_seconds(target)
        if not 20 <= dur <= 1200:
            raise RuntimeError("Unusual music duration for "+path+": "+str(dur))
        tracks.append({
            "title":Path(path).stem,
            "source_path":path,
            "local_file":filename,
            "mood_candidate":mood,
            "source_url":"https://github.com/"+UPSTREAM+"/blob/"+PIN+"/"+quote(path,safe="/"),
            "download_source":uri,
            "license":"CC0-1.0 DECLARED BY ARCHIVE; third-party rights unverified",
            "license_url":"https://github.com/"+UPSTREAM+"/blob/"+PIN+"/LICENSE",
            "git_blob_sha1":expected_sha,
            "sha256":hashlib.sha256(data).hexdigest(),
            "size_bytes":len(data),
            "duration_s":round(dur,3),
            "instrumental_verified":False,
            "rights_status":"ARCHIVE_CC0_DECLARED_NOT_INDEPENDENTLY_AUDITED",
        })
        print("OK",path,len(data),"bytes",round(dur,1),"s",flush=True)
    result={
        "schema":"wap_freepd_public_sources/1",
        "commit":PIN,
        "archive":UPSTREAM,
        "license_git_blob_sha1":LICENSE_GIT_SHA,
        "license_sha256":hashlib.sha256(license_bytes).hexdigest(),
        "license_download_source":license_source,
        "created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "status":"EXACT_MP3_BYTES_VERIFIED; ARTISTIC_AND_VOCAL_REVIEW_PENDING",
        "tracks":tracks,
        "notice":"No original private footage, voices, keys, or other DLM assets in this public artifact.",
    }
    (ROOT/"MANIFEST.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("SUCCESS: cached",len(tracks),"distinct source files",flush=True)

if __name__=="__main__":
    main()
