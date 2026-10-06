"""Generate ArcGIS-flattened metadata XML for APNEP output rasters.

Writes <raster>.tif.xml sidecars that ArcGIS Pro auto-reads. Also supports
direct File Geodatabase import and AGOL-ready standalone XML collection.

Quick reference (run from project root):

  # .tif.xml sidecars alongside each GeoTIFF in data/outputs/
  python scripts/metadata/generate_iso_metadata.py

  # Standalone XML collected to a folder (for AGOL upload)
  python scripts/metadata/generate_iso_metadata.py --outdir data/phase1_agol_metadata

  # Import directly into an existing File Geodatabase (requires arcpy):
  "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" scripts/metadata/generate_iso_metadata.py --gdb deliverables/phase1/arcgis_pro_project/APNEP_Phase1/APNEP_Phase1.gdb

  # With pixi (standalone only — pixi does not include arcpy):
  pixi run -e processing python scripts/metadata/generate_iso_metadata.py
  pixi run -e processing python scripts/metadata/generate_iso_metadata.py --outdir data/phase1_agol_metadata

See also: scripts/README.md
"""

from __future__ import annotations

import argparse
import subprocess
from datetime import date
from pathlib import Path

import rasterio
import yaml
from pyproj import Transformer


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _esc(s):
    if not s:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# Raster bounds reader
# ---------------------------------------------------------------------------
def _read_raster_bounds(raster_path):
    with rasterio.open(raster_path) as src:
        bounds = src.bounds
        crs = src.crs
        if crs and crs.to_epsg() != 4326:
            transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
            west, south = transformer.transform(bounds.left, bounds.bottom)
            east, north = transformer.transform(bounds.right, bounds.top)
        else:
            west, south, east, north = bounds.left, bounds.bottom, bounds.right, bounds.top
    return west, south, east, north


# ---------------------------------------------------------------------------
# Per-raster config assembler
# ---------------------------------------------------------------------------
def _build_raster_cfg(cfg, entry, weights_path):
    key = entry["config_key"]
    titles = cfg.get("description", {}).get("titles", {})
    abstracts = cfg.get("description", {}).get("abstracts", {})
    temporal_cfg = cfg.get("temporal", {})
    lineage_cfg = cfg.get("lineage", {})

    methodology = lineage_cfg.get(entry["lineage_key"], {}).get("description", "")
    sources = _load_sources_from_weights(weights_path, entry["lineage_key"]) if entry["lineage_key"] in ("conservation", "enhancement") else ""
    known_issues = cfg.get("known_issues", "").strip()
    known_line = f"Known issues: {known_issues}" if known_issues else ""
    code_url = cfg.get("citation", {}).get("code_url", "").strip()
    code_line = f"Analysis code: {code_url} (commit {_get_git_short_sha()})." if code_url else ""
    lineage_text = "\n".join(filter(None, [methodology, sources, known_line, code_line]))

    return {
        "title": titles.get(key, key),
        "abstract": abstracts.get(key, ""),
        "temporal": temporal_cfg.get(entry["temporal_key"], {}),
        "lineage": lineage_text,
        "attribute_description": cfg.get("content", {}).get(key, {}).get("attribute_description", ""),
        "content_type": cfg.get("content", {}).get(key, {}).get("content_type", "thematicClassification"),
    }


# ---------------------------------------------------------------------------
# ArcGIS numeric codes for config string values
# ---------------------------------------------------------------------------
ARCGIS_CONTENT_TYPE = {"thematicClassification": "002", "image": "001", "physicalMeasurement": "003"}
ARCGIS_TOPIC_CATEGORY = {
    "environment": "007", "inlandWaters": "012", "farming": "001", "biota": "002",
    "boundaries": "003", "climatologyMeteorologyAtmosphere": "004", "economy": "005",
    "elevation": "006", "geoscientificInformation": "008", "health": "009",
    "imageryBaseMapsEarthCover": "010", "intelligenceMilitary": "011",
    "location": "013", "oceans": "014", "planningCadastre": "015",
    "society": "016", "structure": "017", "transportation": "018",
    "utilitiesCommunication": "019",
}
ARCGIS_STATUS = {"completed": "001", "onGoing": "004", "planned": "005", "underDevelopment": "007"}
ARCGIS_MAINTENANCE = {
    "continual": "001", "daily": "002", "weekly": "003", "monthly": "005",
    "annually": "008", "asNeeded": "009", "irregular": "010", "notPlanned": "011",
}
ARCGIS_ROLE_CODE = {
    "principalInvestigator": "008", "originator": "006", "pointOfContact": "007",
    "custodian": "002", "resourceProvider": "001", "owner": "003",
    "user": "004", "distributor": "005", "processor": "009",
    "publisher": "010", "author": "011",
}
COUNTRY_CODE = {"United States": "US"}


# ---------------------------------------------------------------------------
# ArcGIS-flattened builder
# ---------------------------------------------------------------------------
def build_metadata_xml_arcgis(raster_path, cfg, raster_cfg):
    west, south, east, north = _read_raster_bounds(raster_path)
    stem = Path(raster_path).stem
    today_iso = date.today().isoformat()
    today_compact = date.today().strftime("%Y%m%d")
    pub_date = cfg.get("citation", {}).get("pub_date", str(date.today().year))
    c = cfg.get("contact", {})
    kw_cfg = cfg.get("keywords", {})
    theme_kw = kw_cfg.get("theme", [])
    place_kw = kw_cfg.get("place", [])
    use_lim = cfg.get("use_limitations", "").strip()
    license_text = cfg.get("license", {}).get("use_constraints", "").strip()
    temporal = raster_cfg.get("temporal", {})
    credit_text = cfg.get("credits", "")
    summary_text = cfg.get("project_description", "").strip()

    theme_keys = "".join("<keyword>%s</keyword>" % _esc(kw) for kw in theme_kw)
    place_keys = "".join("<keyword>%s</keyword>" % _esc(kw) for kw in place_kw)

    p = []
    p.append('<?xml version="1.0" encoding="UTF-8"?>')
    p.append('<metadata xml:lang="en">')
    p.append('<Esri><CreaDate>%s</CreaDate><ModDate>%s</ModDate>' % (today_compact, today_compact))
    p.append('<ArcGISFormat>1.0</ArcGISFormat>')
    p.append('<ArcGISStyle>ISO 19139 Metadata Implementation Specification</ArcGISStyle>')
    p.append('<ArcGISProfile>ISO19139</ArcGISProfile></Esri>')
    p.append('<mdFileID>%s</mdFileID>' % _esc(stem))
    p.append('<mdDateSt>%s</mdDateSt>' % today_iso)
    p.append('<mdStanName>ISO 19115</mdStanName>')
    p.append('<mdStanVer>ISO19115:2003</mdStanVer>')
    p.append('<mdCharStC>004</mdCharStC>')
    p.append('<mdLang><languageCode value="eng"/></mdLang>')
    p.append('<mdHrLv><ScopeCd value="005"/></mdHrLv>')
    p.append('<mdChar><CharSetCd value="004"/></mdChar>')

    # Metadata contact
    p.append('<mdContact>')
    p.append('<rpIndName>%s</rpIndName>' % _esc(c.get('person', '')))
    p.append('<rpOrgName>%s</rpOrgName>' % _esc(c.get('org', '')))
    p.append('<rpPosName>%s</rpPosName>' % _esc(c.get('position', '')))
    p.append('<rpCntInfo><cntAddress>')
    p.append('<delPoint>%s</delPoint>' % _esc(c.get('delivery_point', '')))
    p.append('<city>%s</city>' % _esc(c.get('city', '')))
    p.append('<adminArea>%s</adminArea>' % _esc(c.get('admin_area', '')))
    p.append('<postCode>%s</postCode>' % _esc(c.get('postal_code', '')))
    cnt_country_md = COUNTRY_CODE.get(c.get('country', ''), c.get('country', ''))
    p.append('<country>%s</country>' % _esc(cnt_country_md))
    p.append('<eMailAdd>%s</eMailAdd>' % _esc(c.get('email', '')))
    p.append('</cntAddress>')
    p.append('<cntOnlineRes><linkage>%s</linkage></cntOnlineRes>' % _esc(c.get('url', '')))
    p.append('</rpCntInfo>')
    role_md = ARCGIS_ROLE_CODE.get(c.get('role', 'principalInvestigator'), '008')
    p.append('<role><RoleCd value="%s"/></role>' % role_md)
    p.append('</mdContact>')

    # Data identification
    p.append('<dataIdInfo>')
    p.append('<idCitation>')
    p.append('<resTitle>%s</resTitle>' % _esc(raster_cfg["title"]))
    p.append('<date><PubDate>%s</PubDate></date>' % pub_date)
    p.append('<citRespParty>')
    p.append('<rpIndName>%s</rpIndName>' % _esc(c.get('person', '')))
    p.append('<rpOrgName>%s</rpOrgName>' % _esc(c.get('org', '')))
    p.append('<rpPosName>%s</rpPosName>' % _esc(c.get('position', '')))
    p.append('<role><RoleCd value="006"/></role>')
    p.append('</citRespParty>')
    p.append('</idCitation>')

    p.append('<idAbs>%s</idAbs>' % _esc(raster_cfg.get("abstract", "")))
    p.append('<idPurp>%s</idPurp>' % _esc(summary_text))
    p.append('<idCredit>%s</idCredit>' % _esc(credit_text))

    status = cfg.get("access", {}).get("status", "completed")
    status_code = ARCGIS_STATUS.get(status, "001")
    p.append(f'<idStatus><ProgCd value="{status_code}"/></idStatus>')
    maintenance = cfg.get("access", {}).get("maintenance", "irregular")
    maint_code = ARCGIS_MAINTENANCE.get(maintenance, "010")
    p.append(f'<resMaint><MaintFreqCd value="{maint_code}"/></resMaint>')

    # Keywords
    p.append('<descKeys>%s<type><KeywordTypeCd value="001"/></type></descKeys>' % theme_keys)
    p.append('<descKeys>%s<type><KeywordTypeCd value="002"/></type></descKeys>' % place_keys)
    all_tags = theme_kw + place_kw
    search_tags = "".join("<keyword>%s</keyword>" % _esc(t) for t in all_tags)
    p.append('<searchKeys>%s</searchKeys>' % search_tags)

    p.append('<spatRpType><SpatRepTypCd value="002"/></spatRpType>')
    p.append('<dataLang><languageCode value="eng"/></dataLang>')
    p.append('<dataChar><CharSetCd value="004"/></dataChar>')
    crs = cfg.get("spatial", {}).get("crs", "EPSG:32119")
    p.append('<spref><horizsys><planar><PlanCoordSys><csName>%s</csName>'
             '</PlanCoordSys></planar></horizsys></spref>' % _esc(crs))
    for topic in kw_cfg.get("iso_topic", []):
        code = ARCGIS_TOPIC_CATEGORY.get(topic, "007")
        p.append(f'<topicCat><TopicCatCd value="{code}"/></topicCat>')
    p.append('<tpCat><TopicCatCd value="002"/></tpCat>')
    p.append('<tpCat><TopicCatCd value="007"/></tpCat>')

    # Resource constraints
    if use_lim:
        p.append('<resConst><Consts><useLimit>%s</useLimit></Consts></resConst>' % _esc(use_lim))
    if license_text:
        p.append('<resConst><LegConsts><othConsts>%s</othConsts></LegConsts></resConst>' % _esc(license_text))
    access_level = cfg.get("license", {}).get("access_level", "public").strip()
    p.append('<resConst><SecConsts><class><ClasscationCd value="001"/></class>')
    p.append(f'<userNote>Data is {access_level}.</userNote></SecConsts></resConst>')

    # Point of contact
    p.append('<idPoC>')
    p.append('<rpIndName>%s</rpIndName>' % _esc(c.get('person', '')))
    p.append('<rpOrgName>%s</rpOrgName>' % _esc(c.get('org', '')))
    p.append('<rpPosName>%s</rpPosName>' % _esc(c.get('position', '')))
    p.append('<rpCntInfo><cntAddress>')
    p.append('<delPoint>%s</delPoint>' % _esc(c.get('delivery_point', '')))
    p.append('<city>%s</city>' % _esc(c.get('city', '')))
    p.append('<adminArea>%s</adminArea>' % _esc(c.get('admin_area', '')))
    p.append('<postCode>%s</postCode>' % _esc(c.get('postal_code', '')))
    cnt_country_poc = COUNTRY_CODE.get(c.get('country', ''), c.get('country', ''))
    p.append('<country>%s</country>' % _esc(cnt_country_poc))
    p.append('<eMailAdd>%s</eMailAdd>' % _esc(c.get('email', '')))
    p.append('</cntAddress>')
    p.append('<cntOnlineRes><linkage>%s</linkage></cntOnlineRes>' % _esc(c.get('url', '')))
    p.append('</rpCntInfo>')
    p.append('<role><RoleCd value="007"/></role>')
    p.append('</idPoC>')

    # Extent
    p.append('<dataExt>')
    p.append('<geoEle><GeoBndBox esriExtentType="search">')
    p.append('<westBL>%s</westBL><eastBL>%s</eastBL>' % (f"{west:.4f}", f"{east:.4f}"))
    p.append('<southBL>%s</southBL><northBL>%s</northBL>' % (f"{south:.4f}", f"{north:.4f}"))
    p.append('<exTypeCode>1</exTypeCode>')
    p.append('</GeoBndBox></geoEle>')
    t_begin = temporal.get('begin', '')
    t_end = temporal.get('end', '')
    if t_begin and t_end and t_begin != t_end:
        p.append('<tempEle><TempExtent><exTemp><TM_Period>')
        p.append('<tmBegin>%s</tmBegin>' % _esc(t_begin))
        p.append('<tmEnd>%s</tmEnd>' % _esc(t_end))
        p.append('</TM_Period></exTemp></TempExtent></tempEle>')
    p.append('</dataExt>')

    p.append('</dataIdInfo>')

    # Distribution
    dist_url = cfg.get("license", {}).get("distribution_url", "").strip()
    if dist_url:
        p.append('<distInfo><distFormat><formatName>GeoTIFF</formatName></distFormat>'
                 '<distTranOps><onLineSrc><linkage>%s</linkage>'
                 '<orFunct><OnFunctCd value="001"/></orFunct>'
                 '</onLineSrc></distTranOps></distInfo>' % _esc(dist_url))
    else:
        p.append('<distInfo><distFormat><formatName>GeoTIFF</formatName></distFormat></distInfo>')

    # Lineage
    p.append('<dqInfo><dataLineage><statement>%s</statement></dataLineage></dqInfo>' % _esc(raster_cfg.get("lineage", "")))

    # Content info
    p.append('<contentInfo><MD_CoverageDescription>')
    p.append('<attributeDescription>%s</attributeDescription>' % _esc(raster_cfg.get("attribute_description", "")))
    content_type = raster_cfg.get("content_type", "thematicClassification")
    ct_code = ARCGIS_CONTENT_TYPE.get(content_type, "002")
    p.append(f'<contentType><CoverageContentTypCd value="{ct_code}"/></contentType>')
    p.append('</MD_CoverageDescription></contentInfo>')

    p.append('</metadata>')

    return "\n".join(p)


# ---------------------------------------------------------------------------
# Raster registry
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

RASTERS = [
    {"path": "data/outputs/wsi/conservation/apnep-wsi-conserve.tif",
     "config_key": "apnep-wsi-conserve", "temporal_key": "conservation", "lineage_key": "conservation"},
    {"path": "data/outputs/wsi/conservation/apnep-wsi-conserve-highsuit.tif",
     "config_key": "apnep-wsi-conserve-highsuit", "temporal_key": "conservation", "lineage_key": "conservation"},
    {"path": "data/outputs/wsi/enhancement/apnep-wsi-enhance.tif",
     "config_key": "apnep-wsi-enhance", "temporal_key": "enhancement", "lineage_key": "enhancement"},
    {"path": "data/outputs/wsi/enhancement/apnep-wsi-enhance-highsuit.tif",
     "config_key": "apnep-wsi-enhance-highsuit", "temporal_key": "enhancement", "lineage_key": "enhancement"},
    {"path": "data/outputs/wsi/combined/apnep-wsi-combine.tif",
     "config_key": "apnep-wsi-combine", "temporal_key": "combined", "lineage_key": "combine"},
    {"path": "data/outputs/opportunity/apnep-oppareas-padusmask.tif",
     "config_key": "apnep-oppareas-padusmask", "temporal_key": "combined", "lineage_key": "opportunity"},
    {"path": "data/outputs/agol/multiband_wsi_county.tif",
     "config_key": "apnep-wsi-popup-multiband", "temporal_key": "combined", "lineage_key": "popup"},
]


def _get_git_short_sha():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def _load_sources_from_weights(weights_path, scenario_key):
    with open(weights_path, encoding="utf-8") as f:
        wcfg = yaml.safe_load(f)
    yaml_key = {"conservation": "conservation_2024", "enhancement": "enhancement_2070"}.get(scenario_key)
    if not yaml_key:
        return ""
    layers = wcfg.get("wsi", {}).get(yaml_key, {}).get("layers", [])
    lines = []
    for layer in layers:
        label = layer.get("label", layer.get("key", ""))
        source = layer.get("source", "")
        weight = layer.get("weight")
        role = "score" if weight is not None else "exclusion"
        if source and "constructed by authors" not in source:
            lines.append(f"  - {label} ({role}): {source}")
    return "\n".join(["Source data:", *lines]) if lines else ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(config_path="data/metadata/iso_metadata_config.yaml",
         weights_path="data/metadata/repro_weight.yaml",
         gdb_path=None,
         outdir=None):
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    sha = _get_git_short_sha()
    print(f"Generating ArcGIS metadata (git: {sha})")
    if outdir:
        Path(outdir).mkdir(parents=True, exist_ok=True)

    generated = []
    for entry in RASTERS:
        raw_path = Path(entry["path"])
        raster_path = raw_path if raw_path.is_absolute() else (_PROJECT_ROOT / raw_path)
        if not raster_path.exists():
            print(f"  SKIP {raster_path.name} (file not found)")
            continue

        raster_cfg = _build_raster_cfg(cfg, entry, weights_path)
        xml_string = build_metadata_xml_arcgis(str(raster_path), cfg, raster_cfg)

        if gdb_path:
            import arcpy
            from arcpy import metadata as md
            import os

            gdb_name_map = {
                "apnep-wsi-conserve": "WSI_Conservation",
                "apnep-wsi-conserve-highsuit": "WSI_Conservation_HighSuitability",
                "apnep-wsi-enhance": "WSI_Enhancement",
                "apnep-wsi-enhance-highsuit": "WSI_Enhancement_HighSuitability",
                "apnep-wsi-combine": "WSI_Combined",
                "apnep-oppareas-padusmask": "Opportunity_Areas",
                "apnep-wsi-popup-multiband": "WSI_Popup_Multiband",
            }
            gdb_name = gdb_name_map.get(entry["config_key"])
            if not gdb_name:
                print(f"  SKIP {entry['config_key']} (no GDB name mapping)")
                continue
            target = os.path.join(gdb_path, gdb_name)
            if not arcpy.Exists(target):
                print(f"  SKIP {gdb_name} (not found in GDB)")
                continue
            try:
                m = md.Metadata(target)
                m.xml = xml_string
                m.save()
                kw_cfg = cfg.get("keywords", {})
                all_tags = kw_cfg.get("theme", []) + kw_cfg.get("place", [])
                m.tags = ",".join(all_tags)
                m.summary = cfg.get("project_description", "").strip()
                m.credits = cfg.get("credits", "")
                m.save()
                generated.append(target)
                print(f"  WROTE metadata to {gdb_name}")
            except Exception as e:
                print(f"  FAILED {gdb_name}: {type(e).__name__}: {e}")
        else:
            # Write .tif.xml sidecar (ArcGIS Pro auto-reads this)
            filename = raster_path.name + ".xml"
            xml_path = Path(outdir) / (raster_path.stem + "_arcgis.xml") if outdir else raster_path.with_name(filename)
            xml_path.write_text(xml_string, encoding="utf-8")
            generated.append(xml_path)
            print(f"  WROTE {xml_path}")

    print(f"\nDone. Processed {len(generated)} datasets.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate ArcGIS metadata for APNEP output rasters")
    parser.add_argument("--config", default="data/metadata/iso_metadata_config.yaml",
                        help="Path to metadata config YAML")
    parser.add_argument("--weights", default="data/metadata/repro_weight.yaml",
                        help="Path to repro_weight.yaml for source citations")
    parser.add_argument("--gdb", default=None,
                        help="Path to File Geodatabase (imports directly into GDB datasets)")
    parser.add_argument("--outdir", default=None,
                        help="Output directory for standalone XML (for AGOL upload)")
    args = parser.parse_args()
    main(args.config, args.weights, args.gdb, args.outdir)
