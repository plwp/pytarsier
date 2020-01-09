FROM debian:buster
FROM python:3.7-buster

RUN echo 'deb http://deb.debian.org/debian buster main contrib non-free' >> /etc/apt/sources.list && cat /etc/apt/sources.list
RUN apt-get update -qq \
    && apt-get install -y -q --no-install-recommends \
           apt-utils \
           bzip2 \
           ca-certificates \
           curl \
           locales \
           unzip \
           git \
           cmake \
    && apt-get clean

ENV ANTSPATH="/opt/ants" \
    PATH="/opt/ants:$PATH" \
    CMAKE_INSTALL_PREFIX=$ANTSPATH

RUN echo "Cloning ANTs repo..." \
    && mkdir ~/code \
    && cd ~/code \
    && git clone --branch v2.3.1 https://github.com/ANTsX/ANTs.git

RUN echo "Building ANTs..." \
    && mkdir -p ~/bin/antsBuild \
    && cd ~/bin/antsBuild \
    && cmake ~/code/ANTs
RUN cd ~/bin/antsBuild/ \
    && make
RUN cd ~/bin/antsBuild/ANTS-build \
    && make install

RUN apt-get install -y fsl

COPY ./requirements.txt /pytarsier/requirements.txt
WORKDIR /pytarsier
RUN pip install -r requirements.txt --src /usr/local/src
COPY . /pytarsier
LABEL org.nrg.commands="[{\"inputs\": [{\"command-line-flag\": \"--fixed_session_id\", \"name\": \"fixed_session_id\", \"default-value\": null, \"sensitive\": null, \"matcher\": null, \"false-value\": null, \"required\": true, \"true-value\": null, \"replacement-key\": \"#FIXED_SESSION_ID#\", \"command-line-separator\": null, \"type\": \"string\", \"description\": \"XNAT ID of the fixed session\"}, {\"command-line-flag\": \"--fixed_scan_id\", \"name\": \"fixed_scan_id\", \"default-value\": \"None\", \"sensitive\": null, \"matcher\": null, \"false-value\": null, \"required\": false, \"true-value\": null, \"replacement-key\": \"#FIXED_SCAN_ID#\", \"command-line-separator\": null, \"type\": \"string\", \"description\": \"XNAT ID of the fixed scan, if not specified orchestrator will guess which scan to use based on number of images and series description\"}, {\"command-line-flag\": \"--floating_session_id\", \"name\": \"floating_session_id\", \"default-value\": null, \"sensitive\": null, \"matcher\": null, \"false-value\": null, \"required\": true, \"true-value\": null, \"replacement-key\": \"#FLOATING_SESSION_ID#\", \"command-line-separator\": null, \"type\": \"string\", \"description\": \"XNAT ID of the floating session\"}, {\"command-line-flag\": \"--floating_scan_id\", \"name\": \"floating_scan_id\", \"default-value\": \"None\", \"sensitive\": null, \"matcher\": null, \"false-value\": null, \"required\": false, \"true-value\": null, \"replacement-key\": \"#FLOATING_SCAN_ID#\", \"command-line-separator\": null, \"type\": \"string\", \"description\": \"XNAT ID of the floating scan, if not specified orchestrator will guess which scan to use based on number of images and series description\"}, {\"command-line-flag\": \"--project\", \"name\": \"project\", \"default-value\": \"Alfred\", \"sensitive\": null, \"matcher\": null, \"false-value\": null, \"required\": false, \"true-value\": null, \"replacement-key\": \"#PROJECT#\", \"command-line-separator\": null, \"type\": \"string\", \"description\": \"XNAT project. Defaults to Alfred. You don't have to enter this if you're using the web interface\"}], \"name\": \"pytarsier-session\", \"command-line\": \"python orchestrator.py #FIXED_SESSION_ID# #FIXED_SCAN_ID# #FLOATING_SESSION_ID# #FLOATING_SCAN_ID# #PROJECT# --host \$XNAT_HOST --user \$XNAT_USER --password \$XNAT_PASS --dicomdir /dicom\", \"outputs\": [], \"image\": \"jarrelscy/pytarsier:latest\", \"override-entrypoint\": true, \"version\": \"1.0\", \"schema-version\": \"1.0\", \"xnat\": [{\"description\": \"Run pytarsier-session on a Session\", \"contexts\": [\"xnat:imageSessionData\"], \"name\": \"pytarsier-session-session\", \"output-handlers\": [], \"label\": null, \"external-inputs\": [{\"provides-value-for-command-input\": null, \"name\": \"session\", \"default-value\": null, \"sensitive\": null, \"matcher\": null, \"required\": true, \"provides-files-for-command-mount\": null, \"replacement-key\": null, \"via-setup-command\": null, \"user-settable\": null, \"load-children\": true, \"type\": \"Session\", \"description\": \"Input session\"}], \"derived-inputs\": [{\"provides-value-for-command-input\": \"fixed_session_id\", \"name\": \"fixed-session-id\", \"default-value\": null, \"sensitive\": null, \"matcher\": null, \"required\": true, \"provides-files-for-command-mount\": null, \"replacement-key\": null, \"via-setup-command\": null, \"derived-from-xnat-object-property\": \"id\", \"user-settable\": null, \"derived-from-wrapper-input\": \"session\", \"load-children\": true, \"type\": \"string\", \"description\": \"The fixed session's id\"}]}], \"mounts\": [{\"writable\": true, \"path\": \"/dicom\", \"name\": \"dicom\"}], \"environment-variables\": {}, \"type\": \"docker\", \"ports\": {}, \"description\": \"Runs pytarsier on a session's scans, and uploads the comparison sequence\"}]"
