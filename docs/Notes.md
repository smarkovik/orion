# Thoughts & Dev notes 

- using multi stage docker image so we limit the docker image footprint & reduce the possibility to have buildtime artefacts in the production image
- for better scaling, I would later think about splitting ingestion and queries. 
- I would map an s3 bucket instead of local folder, for file uploads & storage for the containers. 
- I would use a mechanism (in the product) when a file processing failed, for which I would notify the customer. 
