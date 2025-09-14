# Thoughts & Dev notes 

- using multi stage docker image so we limit the docker image footprint & reduce the possibility to have buildtime artefacts in the production image
- for better scaling, I would later think about splitting ingestion and queries. 
- I would map an s3 bucket instead of local folder, for file uploads & storage for the containers. 
