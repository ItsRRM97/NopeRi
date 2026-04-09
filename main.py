
from src.client.naukri_client import NaukriLoginClient
from src.client.job_client import NaukriJobClient
from dotenv import load_dotenv
import os
load_dotenv()


if __name__ == "__main__":
    # ---------------------------------------------------------------
    # Load credentials from .env file
    # (NAUKRI_USERNAME and NAUKRI_PASSWORD must be set)
    # ---------------------------------------------------------------
    username = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")

    # ---------------------------------------------------------------
    # 1. Login — authenticates and stores session + bearer token
    # ---------------------------------------------------------------
    client = NaukriLoginClient(username, password)
    client.login()

    # ---------------------------------------------------------------
    # 2. Resume upload — uploads a new PDF resume to your profile,provide the file path 
    # ---------------------------------------------------------------
    print(client.update_resume(r"C:/Users/HP/Downloads/my_resume2.pdf"))

    # ---------------------------------------------------------------
    # 3. Profile update — update headline and summary independently
    #    Both fields are optional, pass only what you want to change
    # ---------------------------------------------------------------
    print(client.update_profile(headline="Software Engineer with 2.3 years of experience in backend development using Node.js, Python, AWS, SQL, and NoSQL."
    ))

    print(client.update_profile(summary="this is my summary"))

    # ---------------------------------------------------------------
    # 4. Misc — fetch profile ID and form key (mostly for debugging)
    # ---------------------------------------------------------------
    # print(client.fetch_profile_id())
    # print(client.get_form_key2())

    # ---------------------------------------------------------------
    # 5. Recommended jobs — fetches personalised job listings
    #    based on your Naukri profile
    # ---------------------------------------------------------------
    jc = NaukriJobClient(client)
    jobs = jc.get_recommended_jobs()

  

    # --------------------------------------------------------------- 
    # 6. Job search and jobapply — UNDER WORK (nkparam token not yet solved) //   
    #     
    # ---------------------------------------------------------------
    # job_lis=(jc.search_jobs("python developer", location="pune"))
    # for count, job in enumerate(job_lis):
    #     print(count+1," :-",job.title, " :- ",job.company)