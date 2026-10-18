#!/usr/bin/env python3
"""Public-domain foley media from Wikimedia Commons. No private DLM assets."""
import datetime
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import subprocess

SOURCES = [
  ("File:Metal drop thump.ogg", "light_metal_contact"),
  ("File:Table ventilator.ogg", "equipment_hum_illustration"),
]
OUT=Path("out/commons-foley")
ENDPOINT="https://commons.wikimedia.org/w/api.php"

def get(url, max_bytes=3_000_000):
    req=Request(url,headers={"User-Agent":"DLM-Documentary-Foley-Research/1.0 (noncommercial bot account not required)","Accept":"application/json, audio/ogg"})
    with urlopen(req,timeout=35) as r:
        data=r.read(max_bytes+1)
    if len(data)>max_bytes:raise ValueError("file too large")
    return data

def textfield(d,k):
    x=d.get(k,{})
    return re.sub(r"<[^>]+>","",str(x.get("value","")))

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    artifacts=[]
    for title,key in SOURCES:
        query=urlencode({"action":"query","format":"json","prop":"imageinfo",
                         "titles":title,"iiprop":"url|size|sha1|extmetadata"})
        document=json.loads(get(ENDPOINT+"?"+query))
        pages=list(document.get("query",{}).get("pages",{}).values())
        if len(pages)!=1 or not pages[0].get("imageinfo"):
            raise ValueError("Missing Wikimedia source metadata "+title)
        info=pages[0]["imageinfo"][0]
        meta=info.get("extmetadata",{})
        short=textfield(meta,"LicenseShortName")
        long=textfield(meta,"License")
        if not ("public domain" in short.lower() or short.upper() in ("CC0","CC-ZERO") or long.lower()=="cc0"):
            raise ValueError("Unapproved Wikimedia license: "+repr((title,short,long)))
        url=info["url"]
        if not url.startswith("https://upload.wikimedia.org/wikipedia/commons/"):
            raise ValueError("Wikimedia original media host required")
        raw=get(url,3_000_000)
        if len(raw)!=info["size"]:
            raise ValueError("Wikimedia byte count mismatch")
        h=hashlib.sha1(raw).hexdigest()
        # Wikimedia imageinfo SHA1 can be base36: check if 40-char hex, else
        # retain for provenance and rely on declared size & our SHA256.
        upstream=str(info.get("sha1",""))
        if len(upstream)==40 and re.fullmatch("[a-f0-9]{40}",upstream) and upstream!=h:
            raise ValueError("Wikimedia SHA1 mismatch")
        filename=key+".ogg"
        (OUT/filename).write_bytes(raw)
        p=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(OUT/filename)],capture_output=True,text=True,check=True)
        seconds=float(p.stdout.strip())
        if not 0.1<seconds<120:raise ValueError("unexpected foley duration")
        artifacts.append({"role":key,"title":title,"file_name":filename,
          "source_page":"https://commons.wikimedia.org/wiki/"+title.replace(" ","_"),
          "direct_url":url,"sha256":hashlib.sha256(raw).hexdigest(),"sha1":h,
          "wiki_imageinfo_sha1":upstream,"bytes":len(raw),"duration_s":seconds,
          "license_declared":short,"license_detail":long,
          "license_url":textfield(meta,"LicenseUrl"),
          "author":textfield(meta,"Artist"),
          "usage_limit":"illustrative sound design only; not a site-synchronous documentary recording",
          "rights_note":"Wikimedia uploader metadata; independently audit attribution and source before public monetization"})
        print("DOWNLOADED AND SOURCE-METADATA CHECKED",title,len(raw),short,seconds,flush=True)
    manifest={"schema":"dlm_commons_pd_foley/1","retrieved_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"origin":"Wikimedia Commons","files":artifacts,"notice":"No private DLM media. Public domain or CC0 declaration checked through Commons imageinfo/extmetadata."}
    (OUT/"MANIFEST.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
if __name__=="__main__":
    main()
