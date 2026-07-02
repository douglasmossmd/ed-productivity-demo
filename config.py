import os

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT       = os.path.dirname(BASE_DIR)   # Productivity Data & Stats/
MASTER_CSV      = os.path.join(DATA_ROOT, "master_productivity.csv")
CUBE_FOLDER     = os.path.join(DATA_ROOT, "Profee Cube Data")
REPORTS_DIR     = os.path.join(BASE_DIR,  "reports")
EMAIL_MAP_PATH  = os.path.join(BASE_DIR,  "Provider_Email_Mapping.csv")

DEPARTMENT_NAME = "Emergency Medicine — CCD"
INSTITUTION     = "University of Chicago Medicine"
LOCATION        = "Center for Care and Discovery"
LOCATION_FILTER = "CENTER FOR CARE AND DISCOVERY"

SENDER_EMAIL    = "ed-analytics@uchicagomedicine.org"
EMAIL_SUBJECT   = "Your ED Productivity Report — {period}"
DRY_RUN         = True   # ALWAYS True until ready to send for real

SA_BASE_URL              = "https://www.shiftadmin.com/vuchicag"
SA_CCD_FACILITY_ID       = 1
SA_CCD_FACILITY_KEYWORDS = ["center for care", "ccd"]
SA_NWI_FACILITY_ID       = 2
SA_NWI_FACILITY_KEYWORDS = ["northwest indiana", "nwi", "crown point"]

NAME_ALIASES = {}
