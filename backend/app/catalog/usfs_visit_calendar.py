"""Hash-checked offline USFS clock supplements on immutable catalog rows.

Exact clocks, dual open statuses and unchanged constructed-site identity are
required. Original and current restrictions remain separately attributed. The
October 15–November 13 span is a conservative review policy, never a source claim
of permanent opening or closure. Unverified holiday dates remain unknown.
"""

import argparse
import hashlib
import json
import re
from copy import deepcopy
from datetime import date, datetime, timedelta
from pathlib import Path

from app.routing.visit_calendar import Calendar

SCHEMA = "roadtrips-usfs-visit-calendar-supplements/1"
TRANSFORMATION = "usfs-explicit-clocks-2026-10-15-v1"
POLICY_START = date(2026, 10, 15)
POLICY_END = date(2026, 11, 13)
POLICY_UNKNOWN_DATES = {
    "2026-11-11": "Holiday opening has not been verified; no source closure claimed"
}
MAX_BYTES = 30 * 1024 * 1024
_BASELINE_SHA256 = "f09f0a85a5dbf0cf586c637ffeb99b1472a2098e75127fdc8ee7fb1b4ccf0ce2"
_SELECTED_IDS = (
    "12433",
    "12441",
    "12479",
    "20698",
    "28954",
    "29044",
    "29052",
    "29244",
    "29918",
    "35235",
    "39566",
    "44573",
    "64853",
    "68020",
    "75516",
    "77641",
    "83273",
    "83747",
    "84460",
)
_SOURCES = {
    "public-current": {
        "source_url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0/query?f=json&where=recareaid+IN+%2829244%2C29044%2C28954%2C29052%2C75516%2C83747%2C29918%2C83273%2C35235%2C12479%2C64853%2C39566%2C68020%2C44573%2C77641%2C12433%2C12441%2C84460%2C20698%29&outFields=%2A&returnGeometry=true&outSR=4326&resultRecordCount=100",
        "snapshot_sha256": "0309a0c1486a2fd0f74c6481653e6cac6fb587200f57c9e473ec31da82632571",
        "checked_at": "2026-10-15T19:48:57.989548+00:00",
        "evidence_path": "public-current.body",
        "http_status": 200,
    },
    "construction-current-site-cn": {
        "source_url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0/query?f=json&where=site_cn+IN+%28%2710855.001431%27%2C%2710856.001431%27%2C%2710857.001431%27%2C%2710859.001431%27%2C%2711070010418%27%2C%2711337010450%27%2C%275040.009041%27%2C%275040010553%27%2C%275081.002601%27%2C%275091.001621%27%2C%275124.005851%27%2C%275125.005851%27%2C%275147010450%27%2C%275252.002601%27%2C%275296.002231%27%2C%275320.001621%27%2C%275321.001621%27%2C%27987236010602%27%2C%275339.003721%27%29&outFields=%2A&returnGeometry=true&outSR=4326&resultRecordCount=100",
        "snapshot_sha256": "ac2060aa83109acb8ddf14d75713f3eaf814d23a5e20f37e1c6250843d912825",
        "checked_at": "2026-10-15T19:50:10.758572+00:00",
        "evidence_path": "construction-current-site-cn.body",
        "http_status": 200,
    },
    "usfs-29918-visitor": {
        "source_url": "https://www.fs.usda.gov/recarea/crgnsa/recarea/?recid=29918",
        "snapshot_sha256": "cd9584e1d6367a5c1534e167c9825d18acf5e9ba8e16472bdee9800333a75eff",
        "checked_at": "2026-10-15T19:48:58.233404+00:00",
        "evidence_path": "usfs-29918-visitor.body",
        "http_status": 403,
    },
    "usfs-35235-visitor": {
        "source_url": "https://www.fs.usda.gov/recarea/tonto/recarea/?recid=35235",
        "snapshot_sha256": "75e529fbda4809ef980ff6b83ee8c15186b9486a4485099be0bf0fe97685593a",
        "checked_at": "2026-10-15T19:48:58.291137+00:00",
        "evidence_path": "usfs-35235-visitor.body",
        "http_status": 403,
    },
    "usfs-64853-visitor": {
        "source_url": "https://www.fs.usda.gov/recarea/dbnf/recarea/?recid=64853",
        "snapshot_sha256": "9b823e7be213c4afef84a56f61c08da4c0091dcfdabfe32b39970c4e8c9b9820",
        "checked_at": "2026-10-15T19:48:58.751760+00:00",
        "evidence_path": "usfs-64853-visitor.body",
        "http_status": 403,
    },
    "usfs-39566-visitor": {
        "source_url": "https://www.fs.usda.gov/recarea/dbnf/recarea/?recid=39566",
        "snapshot_sha256": "9bbc7e982d138e36d9c17a9e3324ef43e885614e1334725bfe0b4d747e33f763",
        "checked_at": "2026-10-15T19:48:58.770238+00:00",
        "evidence_path": "usfs-39566-visitor.body",
        "http_status": 403,
    },
    "usfs-20698-visitor": {
        "source_url": "https://www.fs.usda.gov/recarea/inyo/recarea/?recid=20698",
        "snapshot_sha256": "8c6a118b876d8799f34655daec5a5d54f152ab8ca8c00802a0d2d547da30f200",
        "checked_at": "2026-10-15T19:48:59.137000+00:00",
        "evidence_path": "usfs-20698-visitor.body",
        "http_status": 403,
    },
    "original-fs-batch-01": {
        "source_url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0/query?f=json&where=recarea_enable+%3D+%27Y%27+AND+seasonal_operational_status+%3D+%27OPEN%27+AND+site_type+IN+%28%27DAY+USE+AREA%27%2C%27OBSERVATION+SITE%27%2C%27INTERPRETIVE+SITE%27%2C%27INTERPRETIVE+VISITOR+CENTER+%28MAJOR%29%27%2C%27INTERPRETIVE+VISITOR+CENTER+%28MINOR%29%27%2C%27SWIMMING+SITE%27%2C%27WILDLIFE+VIEWING+SITE%27%2C%27PICNIC+SITE%27%2C%27TRAILHEAD%27%29&outFields=%2A&returnGeometry=true&outSR=4326&resultRecordCount=1000&orderByFields=objectid&resultOffset=1000",
        "snapshot_sha256": "0fa87796f1b13142c2575199f3ced061eb0ecb7a40e08125ea36c246aea36789",
        "checked_at": "2026-10-15T15:48:49.134212+00:00",
        "evidence_path": "original/fs-batch-01.json",
        "http_status": 200,
    },
    "original-fs-expanded-public-02": {
        "source_url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0/query?f=json&where=recareaid+IN+%2828576%2C28578%2C28580%2C28592%2C28612%2C28614%2C28620%2C28624%2C28678%2C28680%2C28954%2C29044%2C29052%2C29074%2C29080%2C29082%2C29154%2C29166%2C29172%2C29200%2C29244%2C29886%2C29892%2C29898%2C29902%2C29918%2C29934%2C29958%2C29960%2C29996%2C30095%2C30103%2C30364%2C30490%2C30656%2C30836%2C30848%2C30856%2C30902%2C31072%2C31078%2C31214%2C31302%2C31358%2C31388%2C31516%2C31562%2C31582%2C31594%2C31696%2C31732%2C31768%2C31802%2C31826%2C31988%2C32004%2C32010%2C32016%2C32018%2C32022%2C32024%2C32026%2C32034%2C32050%2C32062%2C32064%2C32072%2C32082%2C32084%2C32086%2C32090%2C32092%2C32096%2C32100%2C32104%2C32112%2C32118%2C32132%2C32136%2C32138%2C32142%2C32144%2C32146%2C32150%2C32154%2C32160%2C32166%2C32184%2C32332%2C32382%2C32430%2C32446%2C32498%2C32866%2C33036%2C33088%2C33718%2C33728%2C33868%2C33906%29&outFields=%2A&returnGeometry=true&outSR=4326&orderByFields=recareaid",
        "snapshot_sha256": "65a48c1dc53f1113a13dbae573cafde274decdf7e149c35c6766e7e88e01226d",
        "checked_at": "2026-10-15T15:40:14.597101+00:00",
        "evidence_path": "original/fs-expanded-public-02.json",
        "http_status": 200,
    },
    "original-fs-batch-02": {
        "source_url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0/query?f=json&where=recarea_enable+%3D+%27Y%27+AND+seasonal_operational_status+%3D+%27OPEN%27+AND+site_type+IN+%28%27DAY+USE+AREA%27%2C%27OBSERVATION+SITE%27%2C%27INTERPRETIVE+SITE%27%2C%27INTERPRETIVE+VISITOR+CENTER+%28MAJOR%29%27%2C%27INTERPRETIVE+VISITOR+CENTER+%28MINOR%29%27%2C%27SWIMMING+SITE%27%2C%27WILDLIFE+VIEWING+SITE%27%2C%27PICNIC+SITE%27%2C%27TRAILHEAD%27%29&outFields=%2A&returnGeometry=true&outSR=4326&resultRecordCount=1000&orderByFields=objectid&resultOffset=2000",
        "snapshot_sha256": "ffa1dc959f6b51648230af99ecfce366ff33a1aa6a2167a1a98425b00e75e4c8",
        "checked_at": "2026-10-15T15:48:50.702884+00:00",
        "evidence_path": "original/fs-batch-02.json",
        "http_status": 200,
    },
    "original-fs-batch-04": {
        "source_url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0/query?f=json&where=recarea_enable+%3D+%27Y%27+AND+seasonal_operational_status+%3D+%27OPEN%27+AND+site_type+IN+%28%27DAY+USE+AREA%27%2C%27OBSERVATION+SITE%27%2C%27INTERPRETIVE+SITE%27%2C%27INTERPRETIVE+VISITOR+CENTER+%28MAJOR%29%27%2C%27INTERPRETIVE+VISITOR+CENTER+%28MINOR%29%27%2C%27SWIMMING+SITE%27%2C%27WILDLIFE+VIEWING+SITE%27%2C%27PICNIC+SITE%27%2C%27TRAILHEAD%27%29&outFields=%2A&returnGeometry=true&outSR=4326&resultRecordCount=1000&orderByFields=objectid&resultOffset=4000",
        "snapshot_sha256": "b9d8c83f625cd286c2bbe2ec4f18cc34f162bb58c10e9447f507e8a601d4c040",
        "checked_at": "2026-10-15T15:48:56.680840+00:00",
        "evidence_path": "original/fs-batch-04.json",
        "http_status": 200,
    },
    "original-fs-batch-05": {
        "source_url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0/query?f=json&where=recarea_enable+%3D+%27Y%27+AND+seasonal_operational_status+%3D+%27OPEN%27+AND+site_type+IN+%28%27DAY+USE+AREA%27%2C%27OBSERVATION+SITE%27%2C%27INTERPRETIVE+SITE%27%2C%27INTERPRETIVE+VISITOR+CENTER+%28MAJOR%29%27%2C%27INTERPRETIVE+VISITOR+CENTER+%28MINOR%29%27%2C%27SWIMMING+SITE%27%2C%27WILDLIFE+VIEWING+SITE%27%2C%27PICNIC+SITE%27%2C%27TRAILHEAD%27%29&outFields=%2A&returnGeometry=true&outSR=4326&resultRecordCount=1000&orderByFields=objectid&resultOffset=5000",
        "snapshot_sha256": "84f51742b0448423ed9c3f7b9cebbd3f4dacde56dc818ef3cf4ac7d0dbe7baae",
        "checked_at": "2026-10-15T15:48:59.775604+00:00",
        "evidence_path": "original/fs-batch-05.json",
        "http_status": 200,
    },
    "original-fs-expanded-public-09": {
        "source_url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0/query?f=json&where=recareaid+IN+%2874917%2C74923%2C74927%2C74931%2C74941%2C74943%2C74947%2C74949%2C74953%2C74957%2C74959%2C75242%2C75341%2C75413%2C75425%2C75516%2C75562%2C75898%2C76001%2C76178%2C76210%2C77420%2C77442%2C77506%2C77641%2C77742%2C78498%2C78540%2C78542%2C78552%2C78642%2C78659%2C78664%2C78668%2C78687%2C78696%2C78707%2C78747%2C78753%2C78754%2C78762%2C78788%2C78804%2C78818%2C78866%2C78878%2C78882%2C78930%2C78945%2C78964%2C78970%2C78995%2C79016%2C79039%2C79043%2C79123%2C79161%2C79178%2C79478%2C79522%2C79529%2C79586%2C80018%2C80092%2C80110%2C80120%2C80129%2C80211%2C80269%2C80275%2C80278%2C80281%2C80329%2C80450%2C80479%2C80549%2C80584%2C80607%2C80610%2C80783%2C80785%2C80818%2C80842%2C80939%2C80942%2C81049%2C81086%2C81163%2C81164%2C81177%2C81178%2C81179%2C81235%2C81237%2C81242%2C81284%2C81359%2C81360%2C81362%2C81394%29&outFields=%2A&returnGeometry=true&outSR=4326&orderByFields=recareaid",
        "snapshot_sha256": "8a6f3ae1293a4254d13f55c38cd2c721a268d48a3567760aac909abb450def22",
        "checked_at": "2026-10-15T15:40:17.632456+00:00",
        "evidence_path": "original/fs-expanded-public-09.json",
        "http_status": 200,
    },
    "original-fs-batch-03": {
        "source_url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0/query?f=json&where=recarea_enable+%3D+%27Y%27+AND+seasonal_operational_status+%3D+%27OPEN%27+AND+site_type+IN+%28%27DAY+USE+AREA%27%2C%27OBSERVATION+SITE%27%2C%27INTERPRETIVE+SITE%27%2C%27INTERPRETIVE+VISITOR+CENTER+%28MAJOR%29%27%2C%27INTERPRETIVE+VISITOR+CENTER+%28MINOR%29%27%2C%27SWIMMING+SITE%27%2C%27WILDLIFE+VIEWING+SITE%27%2C%27PICNIC+SITE%27%2C%27TRAILHEAD%27%29&outFields=%2A&returnGeometry=true&outSR=4326&resultRecordCount=1000&orderByFields=objectid&resultOffset=3000",
        "snapshot_sha256": "1843cbff2c689ed91cb0e8782fbdf4abca29107c0709ae92281e6717e577edb4",
        "checked_at": "2026-10-15T15:48:54.967621+00:00",
        "evidence_path": "original/fs-batch-03.json",
        "http_status": 200,
    },
    "original-fs-expanded-public-10": {
        "source_url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0/query?f=json&where=recareaid+IN+%2881397%2C81410%2C81438%2C81439%2C81447%2C81448%2C81465%2C81474%2C81475%2C81481%2C81548%2C81550%2C81565%2C81596%2C81607%2C81683%2C81685%2C81689%2C81757%2C81783%2C81830%2C81840%2C81854%2C82063%2C82115%2C82339%2C82358%2C82360%2C82367%2C82368%2C82369%2C82376%2C82377%2C82378%2C82379%2C82380%2C82381%2C82390%2C82404%2C82412%2C82444%2C82486%2C82537%2C82551%2C82559%2C82835%2C82946%2C82974%2C82975%2C82984%2C82987%2C83038%2C83076%2C83095%2C83171%2C83269%2C83273%2C83464%2C83524%2C83544%2C83744%2C83747%2C84210%2C84254%2C84257%2C84268%2C84274%2C84278%2C84280%2C84300%2C84314%2C84460%2C84666%2C84705%29&outFields=%2A&returnGeometry=true&outSR=4326&orderByFields=recareaid",
        "snapshot_sha256": "4b35e619be94e5e467ce172bdcab7385b8e931a1e54f4979709face1942c6854",
        "checked_at": "2026-10-15T15:40:17.935028+00:00",
        "evidence_path": "original/fs-expanded-public-10.json",
        "http_status": 200,
    },
    "original-fs-expanded-public-03": {
        "source_url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0/query?f=json&where=recareaid+IN+%2833978%2C34026%2C34044%2C34046%2C34773%2C34787%2C34831%2C34839%2C35130%2C35235%2C35245%2C35351%2C35439%2C35579%2C35733%2C35747%2C36593%2C36615%2C36617%2C36635%2C36643%2C36647%2C36655%2C36735%2C36741%2C36767%2C36777%2C36779%2C36795%2C36803%2C36805%2C36827%2C36831%2C36841%2C36859%2C36867%2C36945%2C37077%2C38286%2C38298%2C38302%2C38304%2C38340%2C38384%2C38388%2C38394%2C38396%2C38436%2C38446%2C38468%2C38492%2C38526%2C38582%2C38650%2C38706%2C38708%2C38716%2C38752%2C38758%2C38764%2C38812%2C38824%2C38840%2C38850%2C38866%2C38872%2C39014%2C39056%2C39094%2C39140%2C39196%2C39232%2C39252%2C39278%2C39290%2C39292%2C39310%2C39334%2C39342%2C39412%2C39436%2C39464%2C39466%2C39476%2C39482%2C39488%2C39496%2C39502%2C39514%2C39524%2C39526%2C39534%2C39536%2C39566%2C39608%2C39718%2C39732%2C39736%2C39770%2C39794%29&outFields=%2A&returnGeometry=true&outSR=4326&orderByFields=recareaid",
        "snapshot_sha256": "7640f87d9185ecf111587ba3b397b5252ca3d438b1dfbf20b2cedba0746d7a7a",
        "checked_at": "2026-10-15T15:40:14.890731+00:00",
        "evidence_path": "original/fs-expanded-public-03.json",
        "http_status": 200,
    },
    "original-fs-expanded-public-00": {
        "source_url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0/query?f=json&where=recareaid+IN+%284208%2C4212%2C4311%2C4320%2C4404%2C4486%2C5580%2C5669%2C5735%2C5757%2C5759%2C5818%2C6090%2C6092%2C6097%2C6103%2C6125%2C6126%2C6128%2C6132%2C6139%2C6211%2C6227%2C6228%2C6448%2C6499%2C6512%2C6549%2C6588%2C6790%2C6821%2C6867%2C9228%2C9500%2C10086%2C10274%2C10279%2C10281%2C10282%2C10327%2C10329%2C10464%2C10465%2C10467%2C10516%2C10535%2C10537%2C10540%2C10746%2C10759%2C11183%2C11255%2C11273%2C11280%2C11316%2C11326%2C11422%2C11431%2C11754%2C11779%2C11796%2C11820%2C11826%2C12148%2C12177%2C12179%2C12207%2C12318%2C12324%2C12344%2C12359%2C12360%2C12361%2C12415%2C12416%2C12432%2C12433%2C12436%2C12441%2C12442%2C12443%2C12444%2C12474%2C12479%2C12570%2C12681%2C12692%2C12695%2C12737%2C12752%2C12818%2C12828%2C12890%2C12915%2C12916%2C12924%2C12939%2C13080%2C13095%2C13096%29&outFields=%2A&returnGeometry=true&outSR=4326&orderByFields=recareaid",
        "snapshot_sha256": "3c7df49152b2e30509a2a5ae7f8b7c392bf5fad1ffe78eb60998fef9dc5c5f6e",
        "checked_at": "2026-10-15T15:40:12.835309+00:00",
        "evidence_path": "original/fs-expanded-public-00.json",
        "http_status": 200,
    },
    "original-fs-expanded-public-07": {
        "source_url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0/query?f=json&where=recareaid+IN+%2860925%2C61367%2C61377%2C61405%2C61433%2C61439%2C61646%2C61648%2C61674%2C61680%2C62975%2C63404%2C63634%2C63654%2C63736%2C64849%2C64853%2C64897%2C64925%2C64935%2C64941%2C64947%2C64949%2C64955%2C64963%2C64965%2C64973%2C65043%2C65061%2C65123%2C65131%2C65328%2C65348%2C66084%2C66098%2C66294%2C67000%2C67078%2C67096%2C67130%2C67215%2C67223%2C67253%2C67269%2C67271%2C67273%2C67818%2C67834%2C67836%2C67846%2C67862%2C67894%2C67910%2C67912%2C67922%2C67924%2C67926%2C67954%2C67990%2C67998%2C68020%2C68026%2C69462%2C69490%2C69514%2C69782%2C69792%2C69810%2C69816%2C69822%2C69826%2C69838%2C69882%2C69890%2C69918%2C69922%2C69934%2C70130%2C70164%2C70178%2C70198%2C70206%2C70226%2C70278%2C70344%2C70370%2C70402%2C70414%2C70420%2C70442%2C70512%2C70534%2C70558%2C70634%2C70682%2C70708%2C70718%2C70736%2C70767%2C70774%29&outFields=%2A&returnGeometry=true&outSR=4326&orderByFields=recareaid",
        "snapshot_sha256": "1cfa11b04695963af532f175f16a9550ad3266aa76dfd099018b3ed85e27604b",
        "checked_at": "2026-10-15T15:40:17.057268+00:00",
        "evidence_path": "original/fs-expanded-public-07.json",
        "http_status": 200,
    },
    "original-fs-expanded-public-04": {
        "source_url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0/query?f=json&where=recareaid+IN+%2839804%2C39818%2C39824%2C39826%2C39836%2C39838%2C39948%2C39988%2C39990%2C40002%2C40016%2C40020%2C40026%2C40110%2C40170%2C40274%2C40344%2C40377%2C40397%2C40731%2C41217%2C41243%2C41315%2C41375%2C41383%2C41616%2C41624%2C41653%2C41654%2C41662%2C41800%2C41818%2C41830%2C41832%2C41864%2C41874%2C41952%2C41974%2C42275%2C42325%2C42397%2C42403%2C42415%2C42457%2C42487%2C42489%2C42491%2C42493%2C42495%2C42497%2C42509%2C42545%2C42601%2C42627%2C42675%2C43126%2C43274%2C43340%2C43387%2C43389%2C43393%2C43395%2C43403%2C43421%2C43467%2C43499%2C43507%2C44573%2C44777%2C44835%2C44867%2C44937%2C44983%2C45596%2C45600%2C45690%2C45704%2C47014%2C47046%2C47139%2C47235%2C47247%2C47279%2C47291%2C47301%2C47303%2C47450%2C47538%2C47701%2C47713%2C47743%2C47755%2C47765%2C47773%2C47785%2C47787%2C47889%2C47897%2C47923%2C47931%29&outFields=%2A&returnGeometry=true&outSR=4326&orderByFields=recareaid",
        "snapshot_sha256": "03878615f0bfb238048649f9d072353e3b2785fe7088f3195a66beb21d95106a",
        "checked_at": "2026-10-15T15:40:15.299325+00:00",
        "evidence_path": "original/fs-expanded-public-04.json",
        "http_status": 200,
    },
    "original-fs-batch-00": {
        "source_url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0/query?f=json&where=recarea_enable+%3D+%27Y%27+AND+seasonal_operational_status+%3D+%27OPEN%27+AND+site_type+IN+%28%27DAY+USE+AREA%27%2C%27OBSERVATION+SITE%27%2C%27INTERPRETIVE+SITE%27%2C%27INTERPRETIVE+VISITOR+CENTER+%28MAJOR%29%27%2C%27INTERPRETIVE+VISITOR+CENTER+%28MINOR%29%27%2C%27SWIMMING+SITE%27%2C%27WILDLIFE+VIEWING+SITE%27%2C%27PICNIC+SITE%27%2C%27TRAILHEAD%27%29&outFields=%2A&returnGeometry=true&outSR=4326&resultRecordCount=1000&orderByFields=objectid&resultOffset=0",
        "snapshot_sha256": "81a2d129885335a749feb2b5d34b6d95affebed2db5e6fd1dcc79eedd64212d9",
        "checked_at": "2026-10-15T15:48:48.379483+00:00",
        "evidence_path": "original/fs-batch-00.json",
        "http_status": 200,
    },
    "original-fs-expanded-public-01": {
        "source_url": "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0/query?f=json&where=recareaid+IN+%2813154%2C13289%2C13342%2C13402%2C13946%2C13948%2C14875%2C14951%2C16594%2C18187%2C18191%2C18192%2C18550%2C18572%2C18728%2C18732%2C18804%2C18814%2C18834%2C18934%2C18988%2C20266%2C20270%2C20272%2C20318%2C20328%2C20358%2C20400%2C20404%2C20546%2C20552%2C20558%2C20560%2C20632%2C20664%2C20668%2C20698%2C21722%2C21748%2C21780%2C21806%2C21844%2C22592%2C22594%2C22596%2C22598%2C22644%2C22648%2C22652%2C22718%2C22788%2C22904%2C22962%2C22992%2C23062%2C23070%2C25300%2C25566%2C25612%2C25614%2C25650%2C25652%2C25662%2C25764%2C25792%2C25794%2C26095%2C26119%2C26177%2C26796%2C26822%2C26975%2C27045%2C27057%2C27065%2C27067%2C28210%2C28230%2C28234%2C28252%2C28262%2C28264%2C28274%2C28296%2C28306%2C28310%2C28342%2C28350%2C28384%2C28386%2C28388%2C28394%2C28408%2C28428%2C28476%2C28534%2C28536%2C28566%2C28570%2C28572%29&outFields=%2A&returnGeometry=true&outSR=4326&orderByFields=recareaid",
        "snapshot_sha256": "fe58d734b74cc4225fe2c2af1543144f964c44dcd664137f5acedec35db77cc0",
        "checked_at": "2026-10-15T15:40:13.226807+00:00",
        "evidence_path": "original/fs-expanded-public-01.json",
        "http_status": 200,
    },
}

_PROFILES = {
    "29918": {
        "public_hours": "Daily, 9 am - 5 pm.",
        "construction_hours": None,
        "public_season": "Year-round",
        "construction_season": None,
        "opens": "09:00",
        "closes": "17:00",
        "weekdays": list(range(7)),
    },
    "35235": {
        "public_hours": None,
        "construction_hours": "Day use only: open 6:00 a.m. to 10:00 p.m.",
        "public_season": "Year round",
        "construction_season": None,
        "opens": "06:00",
        "closes": "22:00",
        "weekdays": list(range(7)),
    },
    "64853": {
        "public_hours": "Day use only",
        "construction_hours": "Day use only: open 6:00 a.m. to 10:00 p.m.",
        "public_season": None,
        "construction_season": "Open year-round",
        "opens": "06:00",
        "closes": "22:00",
        "weekdays": list(range(7)),
    },
    "39566": {
        "public_hours": "Thursday through Sunday 10 a.m. to 5 p.m.",
        "construction_hours": "Thursday - Sunday 10 a.m. to 5 p.m.",
        "public_season": None,
        "construction_season": "Open year-round",
        "opens": "10:00",
        "closes": "17:00",
        "weekdays": [3, 4, 5, 6],
    },
    "20698": {
        "public_hours": "Open Daily&nbsp;8:30 a.m.&ndash; 4:30 p.m.<br /><em>(entrance gate closed&nbsp;at 4:15 p.m.)</em>&nbsp; &nbsp;",
        "construction_hours": "Daily 08:30 a.m. - 04:30 p.m.",
        "public_season": None,
        "construction_season": None,
        "opens": "08:30",
        "closes": "16:15",
        "weekdays": list(range(7)),
    },
}
_PUBLIC_FIELDS = (
    "recareaid",
    "infra_cn",
    "latitude",
    "longitude",
    "recareaurl",
    "openstatus",
    "open_season_start",
    "open_season_end",
    "operational_hours",
    "restrictions",
    "reservation_info",
    "feedescription",
    "accessibility",
)
_CONSTRUCTION_FIELDS = (
    "site_cn",
    "usda_portal_id",
    "latitude",
    "longitude",
    "globalid",
    "recarea_enable",
    "seasonal_operational_status",
    "op_status_reason",
    "open_season",
    "season_description",
    "season_name",
    "site_season_start_date",
    "site_season_end_date",
    "operational_hours",
    "restrictions",
    "important_info",
    "site_contact_notes",
    "permit_information",
    "fee_charged",
    "fee_description",
    "passes",
)


def _read(root, path, expected):
    if not isinstance(path, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", path):
        raise ValueError("USFS evidence path is not portable")
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError("USFS evidence missing or escapes root")
    if not 0 < target.stat().st_size <= MAX_BYTES:
        raise ValueError("USFS evidence byte ceiling exceeded")
    raw = target.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("USFS evidence checksum mismatch: " + path)
    return raw


def _features(raw, key, expected=None, *, retained_constructed_page=False):
    payload = json.loads(raw)
    if (
        payload.get("error")
        or payload.get("exceededTransferLimit")
        and not retained_constructed_page
        or payload.get("geometryType") != "esriGeometryPoint"
        or payload.get("spatialReference", {}).get("wkid") != 4326
    ):
        raise ValueError("USFS source error, truncation or unsupported coordinate system")
    result = {}
    for feature in payload["features"]:
        fields = feature["attributes"]
        ident = str(fields[key])
        if ident in result:
            raise ValueError("Duplicate USFS native identity")
        result[ident] = fields
    if not 1 <= len(result) <= 10000 or expected is not None and len(result) != expected:
        raise ValueError("USFS source feature count differs")
    return result


def _load(source_root, reviewed_on):
    if type(reviewed_on) is not date:
        raise ValueError("Explicit review date required")
    root = Path(source_root)
    baseline_raw = _read(root, "baseline557.preview.jsonl", _BASELINE_SHA256)
    total, bodies = len(baseline_raw), {}
    for key, receipt in _SOURCES.items():
        checked = datetime.fromisoformat(receipt["checked_at"])
        if checked.utcoffset() is None or checked.date() > reviewed_on:
            raise ValueError("USFS source acquisition is naive or future dated")
        raw = _read(root, receipt["evidence_path"], receipt["snapshot_sha256"])
        total += len(raw)
        if total > MAX_BYTES:
            raise ValueError("USFS aggregate evidence byte ceiling exceeded")
        bodies[key] = raw
    baseline = [json.loads(line) for line in baseline_raw.decode().splitlines()]
    if len(baseline) != 557 or len({row["source_id"] for row in baseline}) != 557:
        raise ValueError("USFS supplement baseline differs from immutable 557")
    rows = {
        row["source_id"].split(":")[-1]: row
        for row in baseline
        if row["source_id"] in {"usfs:" + ident for ident in _SELECTED_IDS}
    }
    if set(rows) != set(_SELECTED_IDS):
        raise ValueError("USFS selected baseline identities missing")
    public = _features(bodies["public-current"], "recareaid", expected=19)
    constructed = _features(bodies["construction-current-site-cn"], "site_cn", expected=19)
    if set(public) != set(_SELECTED_IDS):
        raise ValueError("USFS current public identities differ")
    old = {}
    for key in bodies:
        if key.startswith("original-"):
            identity = "recareaid" if "public" in key else "site_cn"
            # The original reviewed construction feed was explicitly paginated
            # in fixed 1000-row pages; a page continuation flag is not a truncated
            # new 19-identity lookup. These original page bodies remain hash pinned.
            old[key] = _features(
                bodies[key], identity, retained_constructed_page="public" not in key
            )
    return rows, public, constructed, old, total


def _originals(row, old_sources):
    provenance = row["provenance"][0]
    facts = provenance["published_access_facts"]
    result = {}
    for label in ("construction_feed", "public_feed"):
        fact = facts[label]
        keys = [
            key
            for key, source in _SOURCES.items()
            if key.startswith("original-") and source["snapshot_sha256"] == fact["snapshot_sha256"]
        ]
        if len(keys) != 1:
            raise ValueError("Original USFS receipt body is not uniquely retained")
        key = keys[0]
        if any(
            fact[field] != _SOURCES[key][field]
            for field in ("source_url", "snapshot_sha256", "checked_at")
        ):
            raise ValueError("Original USFS acquisition attribution differs")
        fields = old_sources[key].get(str(fact["record_id"]))
        if fields is None or any(fields.get(k) != v for k, v in fact["fields"].items()):
            raise ValueError("Original USFS source restrictions differ from retained body")
        result[label] = (key, fields, fact)
    return result


def _qualify(ident, row, public, constructed, originals):
    """Return a genuine hold reason; no generic all-day or solar-hour inference."""
    native = row["provenance"][0]
    if (
        str(constructed.get("site_cn")) != native["record_id"]
        or str(constructed.get("usda_portal_id")) != ident
        or str(public.get("recareaid")) != ident
        or public.get("infra_cn") not in (None, native["record_id"])
        or [constructed.get("latitude"), constructed.get("longitude")]
        != [row["latitude"], row["longitude"]]
        or constructed.get("globalid") != native["global_id"]
    ):
        return "Native site_cn, portal identity or unchanged construction coordinates disagree"
    if (
        constructed.get("recarea_enable") != "Y"
        or constructed.get("seasonal_operational_status") != "OPEN"
        or public.get("openstatus") != "open"
    ):
        return "Both current OPEN/open statuses and enabled recreation site are required"
    for label, (_, _, original) in originals.items():
        current = constructed if label == "construction_feed" else public
        if any(current.get(key) != value for key, value in original["fields"].items()):
            return "Original and current source restrictions conflict or require review"
    profile = _PROFILES.get(ident)
    if profile is None:
        text = " ".join(
            str(source.get(key) or "")
            for source in (public, constructed)
            for key in (
                "operational_hours",
                "open_season",
                "open_season_start",
                "open_season_end",
                "season_description",
            )
        ).lower()
        if "sunrise" in text or "sunset" in text:
            return "Solar access and seasonal bounds unresolved; no acquired dated sunrise/sunset clocks"
        if "volunteer" in text or "usually" in text or "can vary" in text:
            return "Conditional or volunteer-dependent hours do not verify a chosen opening time"
        if "summer hours" in text and "winter hours" in text:
            return (
                "Seasonal clock variants lack exact transition dates; no winter boundary inferred"
            )
        if "weather" in text or "snow" in text:
            return "Weather/snow-qualified access and complete daily clocks remain unresolved"
        if "all day" in text:
            return "All-day wording conflicts with day-use restriction; no explicit endpoints or 24h inference"
        return "Year-round/day-use text supplies no complete daily opening clocks; not 24h"
    if (
        public.get("operational_hours") != profile["public_hours"]
        or constructed.get("operational_hours") != profile["construction_hours"]
        or public.get("open_season_start") != profile["public_season"]
        or constructed.get("open_season") != profile["construction_season"]
    ):
        return "Published clocks or source seasons differ from exact reviewed literals"
    for source, keys in (
        (public, ("open_season_end", "reservation_info")),
        (
            constructed,
            (
                "op_status_reason",
                "season_description",
                "season_name",
                "site_season_start_date",
                "site_season_end_date",
                "important_info",
                "site_contact_notes",
                "permit_information",
            ),
        ),
    ):
        if any(source.get(key) not in (None, "") for key in keys):
            return "Source date, seasonal, reservation or negative qualification unresolved"
    if ident == "35235":
        if "no trailers" not in (public.get("restrictions") or "") or "no trailers" not in (
            constructed.get("restrictions") or ""
        ):
            return "Sears Kay no-trailers/day-use restriction not retained"
    elif public.get("restrictions") not in (None, "") or constructed.get("restrictions") not in (
        None,
        "",
    ):
        return "Additional source restriction requires review"
    return None


def _constraint(key, locator, fields, **details):
    return {
        **deepcopy(_SOURCES[key]),
        "extraction_locator": locator,
        "literal_fields": deepcopy(fields),
        **details,
    }


def _constraints(ident, row, public, constructed, originals):
    facts = [
        _constraint(
            "public-current",
            {"kind": "ArcGIS-feature", "recareaid": int(ident)},
            {key: public.get(key) for key in _PUBLIC_FIELDS},
        ),
        _constraint(
            "construction-current-site-cn",
            {"kind": "ArcGIS-feature", "site_cn": constructed["site_cn"]},
            {key: constructed.get(key) for key in _CONSTRUCTION_FIELDS},
        ),
    ]
    for label, (key, _, original) in originals.items():
        facts.append(
            _constraint(
                key,
                {"kind": "ArcGIS-feature", "record_id": original["record_id"], "feed": label},
                original["fields"],
                original_restriction=True,
            )
        )
    visitor = f"usfs-{ident}-visitor"
    if visitor in _SOURCES:
        facts.append(
            _constraint(
                visitor,
                {"kind": "HTTP-response", "status": 403},
                {"status": 403, "calendar_content_acquired": False},
                evidence_role="Visitor HTML unavailable; not support for a positive opening claim; no bypass attempted",
            )
        )
    return facts


def _entry(ident, row, public, constructed, constraints):
    profile = _PROFILES[ident]
    overrides = []
    day = POLICY_START
    while day <= POLICY_END:
        if day.weekday() in profile["weekdays"] and day.isoformat() not in POLICY_UNKNOWN_DATES:
            overrides.append(
                {
                    "date": day.isoformat(),
                    "windows": [
                        {
                            "opens": profile["opens"],
                            "closes": profile["closes"],
                            "end_day_offset": 0,
                        }
                    ],
                }
            )
        day += timedelta(days=1)
    calendar_value = {
        "schema_version": "roadtrips-source-visit-calendar/1",
        "weekly_windows": [],
        "date_overrides": overrides,
        "fixed_starts": [],
        "unknown_reasons": [],
        "source_receipts": deepcopy(constraints),
    }
    Calendar.model_validate(calendar_value)
    return {
        "source_id": "usfs:" + ident,
        "source_visit_calendar": calendar_value,
        "source_constraints": constraints,
        "source_attribution": "USDA Forest Service original and current public recreation/constructed-site factual feeds",
        "transformation": {
            "adapter": TRANSFORMATION,
            "policy_date_start": POLICY_START.isoformat(),
            "policy_date_end": POLICY_END.isoformat(),
            "policy_scope_is_source_publication_or_expiry_claim": False,
            "policy_unknown_dates": deepcopy(POLICY_UNKNOWN_DATES),
            "identity_join": {
                "native_site_cn": row["provenance"][0]["record_id"],
                "current_site_cn": constructed["site_cn"],
                "current_public_recareaid": public["recareaid"],
                "public_infra_cn": public.get("infra_cn"),
                "construction_usda_portal_id": constructed["usda_portal_id"],
                "native_coordinates_unchanged": True,
            },
            "rule": "Exact source clock/weekday intersection within bounded review policy; no annual or 24h extrapolation; every original/current restriction retained",
            "effective_full_visit_deadline": "16:15" if ident == "20698" else profile["closes"],
            "gate_interpretation": "Visitor closing remains 16:30; conservatively complete the full dwell by the separately stated 16:15 entrance-gate cutoff"
            if ident == "20698"
            else None,
            "additional_access_conditions": {
                "day_use_only": ident in {"35235", "64853"},
                "trailers": "prohibited" if ident == "35235" else "unknown",
            },
            "visitor_html_status": 403,
            "admission_price": "unknown",
            "ticket_availability": "unknown",
            "original_catalog_rows_modified": 0,
        },
    }


def build_enrichments(source_root, *, reviewed_on):
    rows, public, constructions, old, size = _load(source_root, reviewed_on)
    entries, ledger = [], []
    for ident in _SELECTED_IDS:
        row, published = rows[ident], public[ident]
        site_cn = row["provenance"][0]["record_id"]
        constructed = constructions.get(site_cn)
        if constructed is None:
            raise ValueError("Native USFS construction identity is missing")
        originals = _originals(row, old)
        reason = _qualify(ident, row, published, constructed, originals)
        constraints = _constraints(ident, row, published, constructed, originals)
        if reason is None:
            entries.append(_entry(ident, row, published, constructed, constraints))
        ledger.append(
            {
                "source_id": row["source_id"],
                "name": row["name"],
                "status": "supplement_available_with_explicit_unknown_dates"
                if reason is None
                else "withheld_unknown",
                "hold_reason": reason,
                "visitor_html_status": 403 if ident in _PROFILES else "not_acquired_in_this_pass",
                "policy_unknown_dates": deepcopy(POLICY_UNKNOWN_DATES) if reason is None else {},
                "source_constraints": constraints,
            }
        )
    return {
        "schema_version": SCHEMA,
        "reviewed_on": reviewed_on.isoformat(),
        "entries": entries,
        "holds": ledger,
        "summary": {
            "reviewed_usfs_records": len(ledger),
            "positive_clock_supplements": len(entries),
            "withheld_unknown": sum(item["status"] == "withheld_unknown" for item in ledger),
            "visitor_html403": 5,
            "pinned_source_files": len(_SOURCES) + 1,
            "pinned_source_bytes": size,
            "baseline557_sha256": _BASELINE_SHA256,
            "source_expiry_claim": False,
            "policy_date_start": POLICY_START.isoformat(),
            "policy_date_end": POLICY_END.isoformat(),
            "original_catalog_rows_modified": 0,
            "ticket_availability": "unknown",
            "admission_price": "unknown",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--reviewed-on", required=True, type=date.fromisoformat)
    args = parser.parse_args()
    result = build_enrichments(args.source_root, reviewed_on=args.reviewed_on)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
