# master-thesis
Code for masterthesis

Run everything with sudo - root is needed for loopback.

1. Run SCAT to listen on loopback, ensure to use correct bus and device.
2. Run controller.py.
3. Beneficial to also use Wireshark to analyze individual packets further. Listen on loopback. To listen on 5G packets use plugin https://github.com/fgsect/scat/blob/master/wireshark/scat.lua in wireshark.


Code currently captures
"
def capture_identifiers(queue):
    """
    Start TShark processes for:
      - LTE Paging
      - LTE SIB1
      - 5G SIB1
      - 4G NAS-EPS (with 'and not icmp')
      - 5G NAS-5GS (with 'and not icmp')
    """
    print("[DEBUG] capture_identifiers started.")

    paging_cmd=[
        "tshark","-i","lo",
        "-Y","lte-rrc.PagingRecord_element and not icmp",
        "-T","fields",
        "-e","frame.number",
        "-e","lte-rrc.m_TMSI",
        "-e","lte-rrc.IMSI_Digit",
        "-E","separator=,", "-l","-Q"
    ]
    sib_cmd=[
        "tshark","-i","lo",
        "-Y","lte-rrc.bCCH_DL_SCH_Message.message and not icmp",
        "-T","fields",
        "-e","frame.number",
        "-e","lte-rrc.MCC_MNC_Digit",
        "-e","lte-rrc.trackingAreaCode",
        "-e","lte-rrc.cellIdentity",
        "-E","separator=,", "-l","-Q"
    ]
    sib_5g_cmd=[
        "tshark","-i","lo",
        "-Y","nr-rrc.bCCH_DL_SCH_Message.message and not icmp",
        "-T","fields",
        "-e","frame.number",
        "-e","nr-rrc.trackingAreaCode",
        "-e","nr-rrc.cellIdentity",
        "-E","separator=,", "-l","-Q"
    ]
    nas_eps_cmd=[
        "tshark","-i","lo",
        "-Y","nas-eps and not icmp",
        "-T","fields",
        "-e","nas-eps.emm.m_tmsi",
        "-e","e212.imsi",
        "-e","e212.assoc.imsi",
        "-e","nas-eps.emm.mme_grp_id",
        "-e","nas-eps.emm.mme_code",
        "-e","nas-eps.nas_msg_emm_type",
        "-E","separator=\t","-l","-Q"
    ]
    nas_5gs_cmd=[
        "tshark","-i","lo",
        "-Y","nas-5gs and not icmp",
        "-T","fields",
        "-e","frame.number",
        "-e","nas-5gs.5g_tmsi",
        "-e","nas-5gs.mm.suci.msin",
        "-e","nas-5gs.mm.imeisv",
        "-e","nas-5gs.mm.message_type",
        "-e","nas-5gs.mm.5gs_reg_type",
        "-E","separator=\t","-l","-Q"
    ]
"

Pagings, SIBs, Attach requests, deattaches, rejects, registration, deregistration, identity responses, mme codes.

GUI currently tracks count, lifespan, connected UE changes.
Would advise to use show top 50 for ID's if tracking is being done - as the application may lag.
