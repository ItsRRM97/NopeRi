
import re


#=====================================================================URLs=========================================================


LOGIN_URL = "https://www.naukri.com/central-login-services/v1/login"
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"
FILE_VALIDATION_URL = "https://filevalidation.naukri.com/file"
DASHBOARD_URL = "https://www.naukri.com/cloudgateway-mynaukri/resman-aggregator-services/v0/users/self/dashboard"
PROFILE_UPDATE_URL= "https://www.naukri.com/cloudgateway-mynaukri/resman-aggregator-services/v1/users/self/fullprofiles"
RESUME_UPDATE_URL_TEMPLATE = "https://www.naukri.com/cloudgateway-mynaukri/resman-aggregator-services/v0/users/self/profiles/{profile_id}/advResume"
JOB_SEARCH_URL = "https://www.naukri.com/jobapi/v3/search"
RECOMMENDED_JOBS_URL = "https://www.naukri.com/jobapi/v4/recommendedjobs"
APPLY_JOB_URL = "https://www.naukri.com/jobapi/v4/job/{job_id}/apply"


 #===================================================================================================================================

FORM_KEY_PATTERNS = [
    re.compile(r'formKey\s*[:=]\s*["\']([A-Za-z0-9]{8,})["\']'),
    re.compile(r'"formKey"\s*:\s*"([A-Za-z0-9]{8,})"'),
]

APP_JS_PATTERN = re.compile(r'<script[^>]+src="([^"]*app_v\d+\.min\.js[^"]*)"')
