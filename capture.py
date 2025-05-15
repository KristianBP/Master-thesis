import subprocess
import threading
from datetime import datetime
from shared_queue import capture_queue

# Keep track of last known SIB info
last_sib1 = {"mcc": None, "mnc": None, "tac": None, "cid": None}

# Global store for MME info (Group and Code)
last_mme_info = {"group": "", "code": ""}

def debug_print(msg):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_str}] [DEBUG] {msg}")

def should_ignore_line(line):
    if not line:
        return True
    low = line.lower()
    return ("cannot find dissector" in low) or ("falling back to data" in low)

def is_valid_imsi(val):
    """
    True if `val` is a 14 or 15‑digit decimal string.
    """
    return isinstance(val, str) and val.isdigit() and len(val) in (14, 15)

def is_valid_mtmsi(val):
    """
    Accept any hex string (with or without 0x) or any decimal string.
    """
    if not val:
        return False
    vv = val.lower()

    # hex with 0x prefix
    if vv.startswith("0x"):
        try:
            int(vv, 16)
            return True
        except ValueError:
            return False

    # pure hex (no 0x)
    if all(c in "0123456789abcdef" for c in vv):
        return True

    # pure decimal
    if vv.isdigit():
        return True

    return False

# ---------------- GSM A IMEISV ----------------
def read_gsm_a_imeisv(proc):
    debug_print("Entered read_gsm_a_imeisv (GSM A IMEISV).")
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()
        if should_ignore_line(line):
            continue
        debug_print(f"[GSM_A_IMEISV] Raw: {line}")
        cols = line.split(",")
        if len(cols) < 2:
            continue
        imeisv_val = cols[1].strip()
        if not imeisv_val:
            continue
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ue_ts = datetime.now().strftime("%d-%m-%y %H:%M:%S")
        packet_info = "Identity Response"
        data_dict = {
            "timestamp": ue_ts,
            "id_type": "IMEISV",
            "id": imeisv_val,
            "packet_info": packet_info,
            "tac": last_sib1["tac"],
            "cid": last_sib1["cid"],
            "mcc": last_sib1["mcc"],
            "mnc": last_sib1["mnc"],
            "mme_group_id": "",
            "mme_code": ""
        }
        capture_queue.put(("nas-eps-ue", data_dict))
        capture_queue.put((
            "IMEISV",
            imeisv_val,
            ts,
            last_sib1["mcc"],
            last_sib1["mnc"],
            last_sib1["tac"],
            last_sib1["cid"],
            packet_info,
            "IMEISV",
            "",
            ""
        ))

# ---------------- LTE Paging ----------------
def read_paging(proc):
    debug_print("Entered read_paging (LTE Paging).")
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()
        if should_ignore_line(line):
            continue

        debug_print(f"[Paging] Raw: {line}")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cols = line.split(",")
        # we expect at least: frame.number, m_TMSI, IMSI_Digit
        if len(cols) < 3:
            continue

        # 1) gather *all* possible TMSI candidates from both cols[1] & cols[2]
        raw_fields = cols[1:3]
        tmsi_candidates = []
        for field in raw_fields:
            for sub in field.split(","):
                sub = sub.strip()
                if not sub:
                    continue
                # any valid hex or decimal string is a TMSI
                if is_valid_mtmsi(sub):
                    tmsi_candidates.append(sub)

        # enqueue each TMSI exactly once
        for tmsi in tmsi_candidates:
            capture_queue.put((
                "m-TMSI",
                tmsi,
                ts,
                last_sib1["mcc"],
                last_sib1["mnc"],
                last_sib1["tac"],
                last_sib1["cid"],
                "Paging",
                "m-TMSI",
                last_mme_info["group"],
                last_mme_info["code"]
            ))

        # 2) separately, pull out any *true* IMSI values (14-15 digit decimal) from the IMSI_Digit field
        imsi_field = cols[2]
        for sub in imsi_field.split(","):
            sub = sub.strip()
            if is_valid_imsi(sub):
                capture_queue.put((
                    "IMSI",
                    sub,
                    ts,
                    None,
                    None,
                    None,
                    None,
                    "Paging",
                    "IMSI",
                    "",
                    ""
                ))


# ---------------- LTE SIB1 ----------------
def read_sib(proc):
    global last_sib1
    debug_print("Entered read_sib (LTE SIB1).")
    prev_key = (last_sib1["mcc"], last_sib1["mnc"], last_sib1["tac"], last_sib1["cid"])
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()
        if should_ignore_line(line):
            continue
        debug_print(f"[SIB] Raw line: {line}")
        cols = line.split(",")
        if len(cols) < 8:
            continue
        mcc = cols[1].strip() + cols[2].strip() + cols[3].strip()
        mnc = cols[4].strip() + cols[5].strip()
        tac = cols[6].strip()
        cid = cols[7].strip()
        new_key = (mcc, mnc, tac, cid)
        changed = (new_key != prev_key)
        last_sib1["mcc"] = mcc
        last_sib1["mnc"] = mnc
        last_sib1["tac"] = tac
        last_sib1["cid"] = cid
        debug_print(f"[SIB] Updated last_sib1 => {last_sib1}")
        if changed:
            prev_key = new_key
            now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            capture_queue.put((
                "CELL",
                cid,
                now_ts,
                mcc,
                mnc,
                tac,
                cid,
                "SIB1 update",
                "CELL",
                "",
                ""
            ))

# ---------------- NSA 5G SIB1 ----------------
def read_sib_5g(proc):
    global last_sib1
    debug_print("Entered read_sib_5g (5G NSA).")
    prev_key = (last_sib1["mcc"], last_sib1["mnc"], last_sib1["tac"], last_sib1["cid"])
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()
        if should_ignore_line(line):
            continue
        debug_print(f"[SIB5G] Raw: {line}")
        cols = line.split(",")
        if len(cols) < 4:
            continue
        mcc_mnc_5g = cols[1].strip()
        tac_5g = cols[2].strip()
        cid_5g = cols[3].strip()
        old = (last_sib1["mcc"], last_sib1["mnc"], last_sib1["tac"], last_sib1["cid"])
        parts = mcc_mnc_5g.split(",")
        if len(parts) >= 5:
            mcc = parts[0] + parts[1] + parts[2]
            mnc = parts[3] + parts[4]
            last_sib1["mcc"] = mcc
            last_sib1["mnc"] = mnc
        last_sib1["tac"] = tac_5g
        last_sib1["cid"] = cid_5g
        debug_print(f"[SIB5G] Updated last_sib1 => {last_sib1}")
        new = (last_sib1["mcc"], last_sib1["mnc"], last_sib1["tac"], last_sib1["cid"])
        if new != old:
            now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            capture_queue.put((
                "CELL",
                cid_5g,
                now_ts,
                last_sib1["mcc"],
                last_sib1["mnc"],
                tac_5g,
                cid_5g,
                "SIB1(5G) update",
                "CELL",
                "",
                ""
            ))

# ---------------- 5G SA SIB1 ----------------
def read_sib_5g_sa(proc):
    global last_sib1
    debug_print("Entered read_sib_5g_sa (5G SA SIB1).")
    prev_key = (last_sib1["mcc"], last_sib1["mnc"], last_sib1["tac"], last_sib1["cid"])
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()
        if not line or should_ignore_line(line):
            continue
        debug_print(f"[SIB5G-SA] Raw: {line}")
        cols = line.split(",")
        if len(cols) < 8:
            continue
        mcc = cols[1].strip() + cols[2].strip() + cols[3].strip()
        mnc = cols[4].strip() + cols[5].strip()
        tac = cols[6].strip()
        cid = cols[7].strip()
        new_key = (mcc, mnc, tac, cid)
        last_sib1["mcc"] = mcc
        last_sib1["mnc"] = mnc
        last_sib1["tac"] = tac
        last_sib1["cid"] = cid
        if new_key != prev_key:
            prev_key = new_key
            now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            debug_print(f"[SIB5G-SA] Updated last_sib1 => {last_sib1}")
            capture_queue.put((
                "CELL",
                cid,
                now_ts,
                mcc,
                mnc,
                tac,
                cid,
                "SIB1(5G-SA) update",
                "CELL",
                "",
                ""
            ))

# ---------------- 5G SA Paging ----------------
def read_5g_paging(proc):
    debug_print("Entered read_5g_paging (5G SA Paging).")
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()
        if should_ignore_line(line):
            continue
        debug_print(f"[5G Paging] Raw: {line}")
        cols = line.split(",")
        if len(cols) < 2:
            continue
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tmsi_5g = cols[1].strip()
        subvals = [x.strip() for x in tmsi_5g.split(",") if x.strip()]
        if not subvals:
            subvals = [""]
        for s in subvals:
            if is_valid_mtmsi(s):
                capture_queue.put((
                    "5G-TMSI",
                    s,
                    ts,
                    last_sib1["mcc"],
                    last_sib1["mnc"],
                    last_sib1["tac"],
                    last_sib1["cid"],
                    "Paging(5G)",
                    "5G-TMSI",
                    last_mme_info["group"],
                    last_mme_info["code"]
                ))

# ---------------- RRC newUE_Identity ----------------
def read_rrc_newueid(proc):
    debug_print("Entered read_rrc_newueid (RRC newUE_Identity).")
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        line = line.strip()
        if should_ignore_line(line):
            continue
        debug_print(f"[RRC-UEID] Raw: {line}")
        cols = line.split(",")
        if len(cols) < 2:
            continue
        new_id = cols[1].strip()
        if not new_id:
            continue
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ue_ts = datetime.now().strftime("%d-%m-%y %H:%M:%S")
        data_dict = {
            "timestamp": ue_ts,
            "id_type": "UE-IDENTITY",
            "id": new_id,
            "packet_info": "RRCReconfiguration",
            "tac": last_sib1["tac"],
            "cid": last_sib1["cid"],
            "mcc": last_sib1["mcc"],
            "mnc": last_sib1["mnc"],
            "mme_group_id": "",
            "mme_code": ""
        }
        capture_queue.put(("nas-eps-ue", data_dict))
        capture_queue.put((
            "NAS-EPS",
            new_id,
            ts,
            last_sib1["mcc"],
            last_sib1["mnc"],
            last_sib1["tac"],
            last_sib1["cid"],
            "RRCReconfiguration",
            "UE-IDENTITY",
            "",
            ""
        ))

# ---------------- NEW: RRC ConnectionRequest processing ----------------
def read_rrc_connreq_merged(proc):
    """
    Reads lines from the RRCConnectionRequest command.
    Expected CSV fields (separated by commas):
      index 0: frame.number
      index 1: lte-rrc.randomValue
      index 2: lte-rrc.mmec
      index 3: lte-rrc.m_TMSI
    We filter out warnings that mention "cannot find dissector" or "falling back to data".
    Then:
      - For randomValue lines: if valid, assign id_type "randomValue".
        The packet_info is just "RRC Setup Request" (no "(randomValue=...)" suffix).
      - For m_TMSI: if valid, assign id_type "m-TMSI".
    Both are posted with packet_info "RRCConnectionRequest".
    We always parse mmec_str as hex => '18' => decimal 24, etc.
    """
    debug_print("Entered read_rrc_connreq_merged.")
    global last_mme_info
    while True:
        line = proc.stdout.readline()
        if not line:
            break
        raw_line = line.strip()
        # Skip any warnings
        if "cannot find dissector" in raw_line.lower() or "falling back to data" in raw_line.lower():
            continue
        debug_print(f"[RRC-CONNREQ] Raw: {raw_line}")

        cols = raw_line.split(",")
        while len(cols) < 4:
            cols.append("")
        frame_str = cols[0].strip()
        randv_str = cols[1].strip()
        mmec_str  = cols[2].strip()
        mtmsi_str = cols[3].strip()

        if not frame_str and not randv_str and not mmec_str and not mtmsi_str:
            continue

        # Always interpret mmec_str as hex
        if mmec_str:
            try:
                mmec_dec = str(int(mmec_str, 16))
                last_mme_info["code"] = mmec_dec
            except:
                pass

        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ue_ts  = datetime.now().strftime("%d-%m-%y %H:%M:%S")

        # randomValue => ID type "randomValue"
        if is_valid_mtmsi(randv_str):
            data_dict_randv = {
                "timestamp": ue_ts,
                "id_type": "randomValue",
                "id": randv_str,
                "packet_info": "RRCConnectionRequest",
                "tac": last_sib1["tac"],
                "cid": last_sib1["cid"],
                "mcc": last_sib1["mcc"],
                "mnc": last_sib1["mnc"],
                "mme_group_id": last_mme_info["group"],
                "mme_code": last_mme_info["code"]
            }
            capture_queue.put(("nas-eps-ue", data_dict_randv))
            capture_queue.put((
                "NAS-EPS",
                randv_str,
                now_ts,
                last_sib1["mcc"],
                last_sib1["mnc"],
                last_sib1["tac"],
                last_sib1["cid"],
                "RRCConnectionRequest",
                "randomValue",
                last_mme_info["group"],
                last_mme_info["code"]
            ))

        # m_TMSI => ID type "m-TMSI"
        if is_valid_mtmsi(mtmsi_str):
            data_dict_mt = {
                "timestamp": ue_ts,
                "id_type": "m-TMSI",
                "id": mtmsi_str,
                "packet_info": "RRCConnectionRequest",
                "tac": last_sib1["tac"],
                "cid": last_sib1["cid"],
                "mcc": last_sib1["mcc"],
                "mnc": last_sib1["mnc"],
                "mme_group_id": last_mme_info["group"],
                "mme_code": last_mme_info["code"]
            }
            capture_queue.put(("nas-eps-ue", data_dict_mt))
            capture_queue.put((
                "NAS-EPS",
                mtmsi_str,
                now_ts,
                last_sib1["mcc"],
                last_sib1["mnc"],
                last_sib1["tac"],
                last_sib1["cid"],
                "RRCConnectionRequest",
                "m-TMSI",
                last_mme_info["group"],
                last_mme_info["code"]
            ))

# ---------------- 4G NAS‐EPS (fixed) ----------------
# capture.py

from datetime import datetime
import subprocess
from shared_queue import capture_queue

def read_nas_eps(proc, queue):
    debug_print("Entered read_nas_eps (4G NAS-EPS).")
    emm_type_map = {
        "0x41": "Attach Request",
        "0x42": "Attach Accept",
        "0x43": "Attach Complete",
        "0x44": "Attach Reject",
        "0x45": "Detach Request",
        "0x46": "Detach Accept",
        "0x47": "TAU Request",
        "0x48": "TAU Accept",
        "0x49": "TAU Complete",
        "0x4a": "TAU Reject",
        "0x4b": "Extended Service Request",
        "0x4c": "Service Reject",
        "0x4d": "GUTI Reallocation Command",
        "0x4e": "GUTI Reallocation Complete",
        "0x4f": "Authentication Request",
        "0x50": "Authentication Response",
        "0x51": "Identity Request",
        "0x52": "Identity Response",
        "0x53": "Security Mode Command",
        "0x54": "Security Mode Complete",
        "0x55": "EMM Status",
        "0x56": "Identity Response",
        "0x57": "Spare",
        "0x61": "EMM Information"
    }
    global last_mme_info, last_sib1

    while True:
        raw = proc.stdout.readline()
        if not raw:
            break
        line = raw.rstrip("\n")
        if not line or should_ignore_line(line):
            continue

        debug_print(f"[NAS-EPS] Raw: {line}")
        cols = line.split("\t")
        if len(cols) < 6:
            parts = line.split()
            if len(parts) == 3:
                m_tmsi, imsi, emm_raw = parts
                assoc = mme_grp = mme_cd = ""
                emm_hex = emm_raw.lower()
            else:
                continue
        else:
            while len(cols) < 6:
                cols.append("")
            m_tmsi, imsi, assoc, mme_grp, mme_cd, emm_raw = [c.strip() for c in cols[:6]]
            emm_hex = emm_raw.lower()

        if mme_grp:
            last_mme_info["group"] = mme_grp
        if mme_cd:
            last_mme_info["code"] = mme_cd

        # split out each packet code
        codes = [c.strip().removeprefix("packet=") for c in emm_hex.split(",") if c.strip()]

        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ue_ts  = datetime.now().strftime("%d-%m-%y %H:%M:%S")

        for code in codes:
            human = emm_type_map.get(code, f"packet={code}") if code.startswith("0x") else f"packet={code}"

            # pick which ID field to show
            if human.lower() == "attach request":
                if is_valid_imsi(imsi):
                    used_type, used_id = "IMSI", imsi
                elif is_valid_imsi(assoc):
                    used_type, used_id = "IMSI", assoc
                elif is_valid_mtmsi(m_tmsi):
                    used_type, used_id = "m-TMSI", m_tmsi
                else:
                    continue
            else:
                if is_valid_imsi(imsi):
                    used_type, used_id = "IMSI", imsi
                elif is_valid_imsi(assoc):
                    used_type, used_id = "IMSI", assoc
                elif is_valid_mtmsi(m_tmsi):
                    used_type, used_id = "m-TMSI", m_tmsi
                else:
                    continue

            # detail tab
            detail = {
                "timestamp": ue_ts,
                "id_type": used_type,
                "id": used_id,
                "packet_info": human,
                "tac": last_sib1["tac"],
                "cid": last_sib1["cid"],
                "mcc": last_sib1["mcc"],
                "mnc": last_sib1["mnc"],
                "mme_group_id": last_mme_info["group"],
                "mme_code": last_mme_info["code"]
            }
            queue.put(("nas-eps-ue", detail))

            # UE-connected tab
            queue.put((
                "NAS-EPS",
                used_id,
                now_ts,
                last_sib1["mcc"],
                last_sib1["mnc"],
                last_sib1["tac"],
                last_sib1["cid"],
                human,
                used_type,
                last_mme_info["group"],
                last_mme_info["code"]
            ))


def read_nas_5gs(proc, queue):
    debug_print("Entered read_nas_5gs (5G SA).")
    msg_type_map = {
        "0x41": "Registration request",
        "0x42": "Registration accept",
        "0x43": "Registration complete",
        "0x45": "Deregistration request",
        "0x46": "Deregistration accept",
        "0x4c": "Service request",
        "0x4e": "Service accept",
        "0x5c": "Identity response",
        "0x61": "EMM Information",
        "0x67": "UL NAS transport",
        "0x68": "DL NAS transport"
    }
    global last_sib1

    def human_msg(code):
        if code in msg_type_map:
            return msg_type_map[code]
        elif code.startswith("0x"):
            return f"packet={code}"
        elif code.lower() == "rrconly":
            return "RRC Setup Request"
        else:
            return f"packet={code}"

    while True:
        raw = proc.stdout.readline()
        if not raw:
            break
        line = raw.rstrip("\n")
        if not line or should_ignore_line(line):
            continue

        debug_print(f"[NAS-5GS] Raw: {line}")
        cols = line.split("\t")
        while len(cols) < 9:
            cols.append("")
        _frame, g_tmsi, msin, imeisv, msg_field, regt, p1, p2, rv = [c.strip() for c in cols]
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # detail-only IMEISV
        for sub in imeisv.split(","):
            sub = sub.strip()
            if sub:
                detail = {
                    "timestamp": datetime.now().strftime("%d-%m-%y %H:%M:%S"),
                    "id_type": "IMEISV",
                    "id": sub,
                    "packet_info": "IMEISV",
                    "tac": last_sib1["tac"],
                    "cid": last_sib1["cid"],
                    "mcc": last_sib1["mcc"],
                    "mnc": last_sib1["mnc"],
                    "mme_group_id": "",
                    "mme_code": ""
                }
                queue.put(("nas-5gs-ue", detail))
                queue.put((
                    "NAS-5GS", sub, ts,
                    last_sib1["mcc"], last_sib1["mnc"],
                    last_sib1["tac"], last_sib1["cid"],
                    "IMEISV", "IMEISV", "", ""
                ))

        # detail-only MSIN
        for sub in msin.split(","):
            sub = sub.strip()
            if sub:
                detail = {
                    "timestamp": datetime.now().strftime("%d-%m-%y %H:%M:%S"),
                    "id_type": "MSIN",
                    "id": sub,
                    "packet_info": "MSIN",
                    "tac": last_sib1["tac"],
                    "cid": last_sib1["cid"],
                    "mcc": last_sib1["mcc"],
                    "mnc": last_sib1["mnc"],
                    "mme_group_id": "",
                    "mme_code": ""
                }
                queue.put(("nas-5gs-ue", detail))
                queue.put((
                    "MSIN", sub, ts,
                    last_sib1["mcc"], last_sib1["mnc"],
                    last_sib1["tac"], last_sib1["cid"],
                    "MSIN", "MSIN", "", ""
                ))

        # randomValue entries
        for rv_val in [x.strip() for x in rv.split(",") if x.strip()]:
            if is_valid_mtmsi(rv_val):
                detail = {
                    "timestamp": datetime.now().strftime("%d-%m-%y %H:%M:%S"),
                    "id_type": "randomValue",
                    "id": rv_val,
                    "packet_info": "RRC Setup Request",
                    "tac": last_sib1["tac"],
                    "cid": last_sib1["cid"],
                    "mcc": last_sib1["mcc"],
                    "mnc": last_sib1["mnc"],
                    "mme_group_id": "",
                    "mme_code": ""
                }
                queue.put(("nas-5gs-ue", detail))
                queue.put((
                    "NAS-5GS", rv_val, ts,
                    last_sib1["mcc"], last_sib1["mnc"],
                    last_sib1["tac"], last_sib1["cid"],
                    "RRC Setup Request", "randomValue", "", ""
                ))

        # Part1, Part2, Combined
        combined = (p1 + p2).strip()
        parts = [
            ("RRC Setup Request (Part1)", p1),
            ("RRC Setup Request (Part2)", p2),
            ("RRC Setup Request", combined)
        ]
        for pkt_name, val in parts:
            if val and is_valid_mtmsi(val):
                detail = {
                    "timestamp": datetime.now().strftime("%d-%m-%y %H:%M:%S"),
                    "id_type": "5G-TMSI",
                    "id": val,
                    "packet_info": pkt_name,
                    "tac": last_sib1["tac"],
                    "cid": last_sib1["cid"],
                    "mcc": last_sib1["mcc"],
                    "mnc": last_sib1["mnc"],
                    "mme_group_id": "",
                    "mme_code": ""
                }
                queue.put(("nas-5gs-ue", detail))
                queue.put((
                    "NAS-5GS", val, ts,
                    last_sib1["mcc"], last_sib1["mnc"],
                    last_sib1["tac"], last_sib1["cid"],
                    pkt_name, "5G-TMSI", "", ""
                ))

        # genuine 5G-TMSI per message code
        tmsis = [x.strip() for x in g_tmsi.split(",") if is_valid_mtmsi(x)]
        codes = [x.strip() for x in msg_field.split(",") if x.strip()]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for tmsi in tmsis:
            for code in codes:
                human = human_msg(code)
                ue_data = {
                    "timestamp": now,
                    "id_type": "5G-TMSI",
                    "id": tmsi,
                    "packet_info": human,
                    "tac": last_sib1["tac"],
                    "cid": last_sib1["cid"],
                    "mcc": last_sib1["mcc"],
                    "mnc": last_sib1["mnc"],
                    "mme_group_id": "",
                    "mme_code": ""
                }
                queue.put(("nas-5gs-ue", ue_data))
                queue.put((
                    "NAS-5GS", tmsi, ts,
                    last_sib1["mcc"], last_sib1["mnc"],
                    last_sib1["tac"], last_sib1["cid"],
                    human, "5G-TMSI", "", ""
                ))



def capture_identifiers(queue):
    debug_print("capture_identifiers started.")

    gsm_a_imeisv_cmd = [
        "tshark", "-i", "lo",
        "-Y", "gsm_a.imeisv and not icmp",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "gsm_a.imeisv",
        "-E", "separator=,", "-l", "-Q"
    ]
    paging_cmd = [
        "tshark", "-i", "lo",
        "-Y", "lte-rrc.PagingRecord_element and not icmp",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "lte-rrc.m_TMSI",
        "-e", "lte-rrc.IMSI_Digit",
        "-E", "separator=,", "-l", "-Q"
    ]
    sib_cmd = [
        "tshark", "-i", "lo",
        "-Y", "lte-rrc.bCCH_DL_SCH_Message.message and not icmp",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "lte-rrc.MCC_MNC_Digit",
        "-e", "lte-rrc.trackingAreaCode",
        "-e", "lte-rrc.cellIdentity",
        "-E", "separator=,", "-l", "-Q"
    ]
    sib5g_cmd = [
        "tshark", "-i", "lo",
        "-Y", "nr-rrc.bCCH_DL_SCH_Message.message and not icmp",
        "-T", "fields",
        "-e", "nr-rrc.MCC_MNC_Digit",
        "-e", "nr-rrc.trackingAreaCode",
        "-e", "nr-rrc.cellIdentity",
        "-E", "separator=,", "-l", "-Q"
    ]
    nas_eps_cmd = [
        "tshark", "-i", "lo",
        "-Y", "nas-eps and not icmp",
        "-T", "fields",
        "-e", "nas-eps.emm.m_tmsi",
        "-e", "e212.imsi",
        "-e", "e212.assoc.imsi",
        "-e", "nas-eps.emm.mme_grp_id",
        "-e", "nas-eps.emm.mme_code",
        "-e", "nas-eps.nas_msg_emm_type",
        "-E", "separator=\t", "-l", "-Q"
    ]
    nas_5gs_cmd = [
        "tshark", "-i", "lo",
        "-Y", "(nas-5gs or nr-rrc.ng_5G_S_TMSI_Part1 or nr-rrc.ng_5G_S_TMSI_Part2 or nr-rrc.randomValue) and not icmp",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "nas-5gs.5g_tmsi",
        "-e", "nas-5gs.mm.suci.msin",
        "-e", "nas-5gs.mm.imeisv",
        "-e", "nas-5gs.mm.message_type",
        "-e", "nas-5gs.mm.5gs_reg_type",
        "-e", "nr-rrc.ng_5G_S_TMSI_Part1",
        "-e", "nr-rrc.ng_5G_S_TMSI_Part2",
        "-e", "nr-rrc.randomValue",
        "-E", "separator=\t", "-l", "-Q"
    ]
    sa_paging_cmd = [
        "tshark", "-i", "lo",
        "-Y", "nr-rrc.pagingRecordList and not icmp",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "nr-rrc.ng_5G_S_TMSI",
        "-E", "separator=,", "-l", "-Q"
    ]
    sib5g_sa_cmd = [
        "tshark", "-i", "lo",
        "-Y", "nr-rrc and not icmp",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "nr-rrc.MCC_MNC_Digit",
        "-e", "nr-rrc.trackingAreaCode",
        "-e", "nr-rrc.cellIdentity",
        "-E", "separator=,", "-l", "-Q"
    ]
    rrc_newueid_cmd = [
        "tshark", "-i", "lo",
        "-Y", "lte-rrc.newUE_Identity and not icmp",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "lte-rrc.newUE_Identity",
        "-E", "separator=,", "-l", "-Q"
    ]
    # EXACT command that works for RRCConnectionRequest:
    rrc_connreq_merged_cmd = [
        "tshark", "-i", "lo",
        "-Y", "lte-rrc.rrcConnectionRequest_element and not icmp",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "lte-rrc.randomValue",
        "-e", "lte-rrc.mmec",
        "-e", "lte-rrc.m_TMSI",
        "-E", "separator=,", "-l"
    ]

    debug_print("Starting TShark subprocesses.")

    from threading import Thread

    # Send other TShark processes' stderr to DEVNULL so warnings don't clutter
    p_gsm_a = subprocess.Popen(gsm_a_imeisv_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               bufsize=1, universal_newlines=True)
    p_paging = subprocess.Popen(paging_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                bufsize=1, universal_newlines=True)
    p_sib = subprocess.Popen(sib_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             bufsize=1, universal_newlines=True)
    p_sib5g = subprocess.Popen(sib5g_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               bufsize=1, universal_newlines=True)
    p_nas = subprocess.Popen(nas_eps_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             bufsize=1, universal_newlines=True)
    p_5gs = subprocess.Popen(nas_5gs_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             bufsize=1, universal_newlines=True)
    p_sa_pg = subprocess.Popen(sa_paging_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               bufsize=1, universal_newlines=True)
    p_sib5g_sa = subprocess.Popen(sib5g_sa_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  bufsize=1, universal_newlines=True)
    p_rrc_nu = subprocess.Popen(rrc_newueid_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                bufsize=1, universal_newlines=True)

    # For the RRC ConnectionRequest command, merge stderr→stdout so we can parse lines
    p_connreq_merged = subprocess.Popen(
        rrc_connreq_merged_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1, universal_newlines=True
    )

    t_gsm_a = Thread(target=read_gsm_a_imeisv, args=(p_gsm_a,))
    t_pg    = Thread(target=read_paging, args=(p_paging,))
    t_sib_  = Thread(target=read_sib, args=(p_sib,))
    t_sib5g = Thread(target=read_sib_5g, args=(p_sib5g,))
    t_ne    = Thread(target=read_nas_eps, args=(p_nas, capture_queue))
    t_n5    = Thread(target=read_nas_5gs, args=(p_5gs, capture_queue))
    t_sa_pg = Thread(target=read_5g_paging, args=(p_sa_pg,))
    t_sib5g_sa = Thread(target=read_sib_5g_sa, args=(p_sib5g_sa,))
    t_rrc_nu = Thread(target=read_rrc_newueid, args=(p_rrc_nu,))
    t_connreq_merged = Thread(target=read_rrc_connreq_merged, args=(p_connreq_merged,))

    # Start threads
    t_gsm_a.start()
    t_pg.start()
    t_sib_.start()
    t_sib5g.start()
    t_ne.start()
    t_n5.start()
    t_sa_pg.start()
    t_sib5g_sa.start()
    t_rrc_nu.start()
    t_connreq_merged.start()

    debug_print("Threads running. Press Ctrl+C to stop.")
    try:
        t_gsm_a.join()
        t_pg.join()
        t_sib_.join()
        t_sib5g.join()
        t_ne.join()
        t_n5.join()
        t_sa_pg.join()
        t_sib5g_sa.join()
        t_rrc_nu.join()
        t_connreq_merged.join()
    except KeyboardInterrupt:
        debug_print("KeyboardInterrupt => stopping.")
    finally:
        procs = [
            p_gsm_a, p_paging, p_sib, p_sib5g, p_nas,
            p_5gs, p_sa_pg, p_sib5g_sa, p_rrc_nu, p_connreq_merged
        ]
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait()
        debug_print("capture_identifiers finished.")
