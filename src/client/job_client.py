import logging
from datetime import datetime
from src.models.models import Job
from src.client.naukri_client import NaukriLoginClient
from src.exceptions.exceptions import NaukriAuthError, NaukriParseError
from src.utils.request_helper import with_exponential_retry
import json

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S"))
logger.addHandler(_handler)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_job(raw: dict) -> Job:
    return Job(
        job_id=str(raw.get("jobId") or raw.get("id") or ""),
        title=raw.get("title") or raw.get("jobTitle") or "N/A",
        company=raw.get("companyName") or raw.get("company") or "N/A",
        location=next((p["label"] for p in raw.get("placeholders", []) if p.get("type") == "location"), "N/A"),
        experience=raw.get("experienceText") or raw.get("experience") or "N/A",
        salary=raw.get("salaryDetail") or raw.get("salary") or "Not disclosed",
        posted_date=raw.get("footerPlaceholderLabel") or raw.get("postedDate") or "N/A",
        apply_link=raw.get("jdURL") or f"https://www.naukri.com/job-listings-{raw.get('jobId', '')}",
        description=raw.get("jobDescription") or "",
        tags=[t.strip() for t in raw.get("tagsAndSkills", "").split(",")] if raw.get("tagsAndSkills") else [],
    )
 

def _cluster_dates() -> dict:
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {
        "apply": now,
        "preference": now,
        "profile": now,
        "similar_jobs": now,
    }


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class NaukriJobClient:

    def __init__(self, login_client: NaukriLoginClient):
        if not login_client.session:
            raise NaukriAuthError("Login required")
        self._session = login_client.session
        self._client = login_client
        self.pool_idx=0



        # ------------------------------------------------------------------
        # nkparam token pool
        #
        # Naukri's job-search endpoint (/jobapi/v3/search) requires a signed
        # request header called `nkparam`. This token is generated inside
        # Naukri's obfuscated JS bundle and changes every browser session.
        # Without a valid token the API returns 403 Forbidden.
        #
        # HOW TO HARVEST TOKENS:
        #   1. Run the harvester script:
        #         python nk_param_getter.py
        #      It opens Chrome, visits a Naukri search page, captures the
        #      outgoing nkparam header via Chrome performance logs, and
        #      appends each token on a new line to  nkPool.txt
        #   2. Stop it with Ctrl+C once you have enough tokens (100+ recommended,
        #      1000+ for heavy scraping / auto-apply agents).
        #
        # HOW TO FILL THIS POOL:
        #   Copy the contents of nkPool.txt and paste the tokens as strings
        #   in the list below, one per line.  Example:
        #
        #       self.pool = open("nkPool.txt").read().splitlines()
        #
        #   Or keep them inline here for a self-contained client.
        #
        # TOKEN EXPIRY:
        #   Tokens appear to stay valid for several hours.  If you get a 403
        #   mid-run, the current token has expired — the client will move to
        #   the next one automatically (pool_idx increments in _search_headers).
        #   When the pool is exhausted, run the harvester again.
        #
        # NOTE: never commit real tokens to a public repo.
        #       Add nkPool.txt to .gitignore.
        # ------------------------------------------------------------------


        self.pool=[
            "bndAlb4UcfAvZIVTU+JFCIbi/7UoxgB4rXMEX28ToGmEzqZ5tcN38d2BNJMAw4znfEh8dxzIKB0bp3+H4r31Tw==",
            "cJV9CTLafgFjZ1Xi5ZmCNcrWuL294nHm1d3SyTCFjPCMTgMR/Ki1f39Wf2+zCkb24phmVCPAOXWoFB6DtvF8qg==",
            "Upuflfn5kWb2cDv1J/f3aYbgNIu3224eXpFvq3Yi4TJv/ufjg/m1STwSmsyH1WOUk8nfoHqu2KSWRc4p2kouFA==",
            "NIR/oU7L3AicyjhH/iW6fe9xLto2KG7KvFL9t2EDi7seBlb6jVvze7N9cGQQ16GrbxavfL+zg1TesKdM/iH97A==",
            "kQwinwhu3BT8Poi5YQUd1SzY8KYgjys2/bVg2pQkQd15rGeIOcTRld/qjuQuZ8pLUp0qzkUPZ3t7h6VW3OCWUw=="
            ]

    def _headers(self):
        return self._client._build_headers(auth=True)
   
    def format_jobs(self, raw_jobs):
        formatted = []

        for job in raw_jobs:
            # Extract placeholders safely
            exp = sal = loc = ""

            for item in job.get("placeholders", []):
                if item.get("type") == "experience":
                    exp = item.get("label")
                elif item.get("type") == "salary":
                    sal = item.get("label")
                elif item.get("type") == "location":
                    loc = item.get("label")

            formatted.append({
                "title": job.get("title"),
                "company": job.get("companyName"),
                "experience": exp,
                "location": loc,
                "salary": sal,
                "skills": job.get("tagsAndSkills", "").split(","),
                "job_url": "https://www.naukri.com" + job.get("jdURL", ""),
                "posted": job.get("footerPlaceholderLabel")
            })

        return formatted
    def _search_headers(self):
        # nkparam is a static captured token — see search_jobs() docstring
        headers = self._client._build_headers(auth=False)
        headers.update({
            "authority":        "www.naukri.com",
            "accept":           "application/json",
            "accept-encoding":  "gzip, deflate, br, zstd",
            "accept-language":  "en-US,en;q=0.9",
            "appid":            "109",
            "gid":              "LOCATION,INDUSTRY,EDUCATION,FAREA_ROLE",
            "nkparam":         f"{self.pool[self.pool_idx]}" 

           
        })
        self.pool_idx+=1
        return headers

    # ------------------------------------------------------------------
    # Recommended jobs
    # ------------------------------------------------------------------




    def apply_job(self, job: Job, apply_data: dict | None = None):
        """
        Apply to a single job
        """
        url = "https://www.naukri.com/cloudgateway-workflow/workflow-services/apply-workflow/v1/apply"

        if not job.job_id:
            raise ValueError("Invalid job_id")

        body = {
            "strJobsarr": [job.job_id]  # single job as array
        }

        if apply_data:
            body["applyData"] = apply_data

        body_str = json.dumps(body)

        # Same payload structure as JS
        full_body = (
            f'{body_str},'
            '"logstr":"--drecomm_profile-2-F-0-1--17140801091455348-",'
            '"flowtype":"show",'
            '"crossdomain":true,'
            '"jquery":1,'
            '"rdxMsgId":"",'
            '"chatBotSDK":true,'
            '"mandatory_skills":["CSS","HTML","React.Js"],'
            '"optional_skills":["Typescript","Angular"],'
            '"applyTypeId":"107",'
            '"closebtn":"y",'
            '"applySrc":"drecomm_profile",'
            '"sid":"17140801091455348",'
            '"mid":""}'
        )

        logger.debug(f"Applying to job: {job.job_id}")

        res = self._session.post(
            url,
            headers=self._headers(),
            data=full_body
        )

        try:
            data = res.json()
        except Exception:
            raise NaukriParseError(f"Invalid JSON response: {res.text}")

        if res.status_code in (401, 403):
            raise NaukriAuthError(data.get("message", "Auth failed"))

        if not data.get("jobs"):
            raise Exception("Already applied or failed")

        return data
    def get_recommended_jobs(self) -> list[Job]:
        """Fetches recommended jobs using the cluster-based API."""
        url = "https://www.naukri.com/jobapi/v2/search/recom-jobs"

        res = self._session.post(
            url,
            headers=self._headers(),
            json={
                "clusterId": None,
                "src": "recommClusterApi",
                "clusterSplitDate": _cluster_dates(),
            },
        )

        if not res.ok:
            raise NaukriParseError(f"Recommended jobs fetch failed: {res.status_code}")

        data = res.json()
        raw_jobs = data.get("jobDetails") or []

        print(raw_jobs[:5])
        return [_parse_job(j) for j in raw_jobs]

    # ------------------------------------------------------------------
    # Search jobs  (UNDER WORK)
    # ------------------------------------------------------------------

    def search_jobs(
        self,
        keyword: str,
        location: str = "",
        page: int = 2,
        experience: int = 2,
        results_per_page: int = 100,
        lat_long: str = "",
    ) -> list[Job]:
        """
        UNDER WORK — currently returns 403.

        Root cause: `nkparam` in _search_headers() is a static token
        captured from browser traffic. It belongs to appid=109 (search)
        and is different from the formKey used elsewhere. Need to
        reverse-engineer how Naukri generates / signs this value from
        the JS bundle before search will work.
        """
        url = "https://www.naukri.com/jobapi/v3/search"
        seo_key = keyword.strip().lower().replace(" ", "-") + "-jobs"

        params = {
            "noOfResults":      results_per_page,
            "urlType":          "search_by_keyword",
            "searchType":       "adv",
            "keyword":          keyword,
            "k":                keyword,
            "pageNo":           page,
            "experience":       experience,
            "nignbevent_src":   "jobsearchDeskGNB",
            "seoKey":           seo_key,
            "src":              "jobsearchDesk",
            "latLong":          lat_long,
        }

        res = self._session.get(url, headers=self._search_headers(), params=params)

        if res.status_code == 403:
            raise NaukriAuthError("403 Forbidden — nkparam token likely expired")

        if res.status_code == 406:
            logger.debug("406 Validation error: %s", res.text)
            return []

        if not res.ok:
            raise NaukriParseError(f"Search failed: {res.status_code} — {res.text}")

        data = res.json()
        raw_jobs = data.get("jobDetails") or data.get("jobs") or []

        oc_list=self.format_jobs(raw_jobs)
        print(oc_list)
        if not raw_jobs:
            logger.debug("No jobs returned for keyword=%r page=%d", keyword, page)
            return []

        return [_parse_job(j) for j in raw_jobs]