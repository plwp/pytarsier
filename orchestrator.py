import argparse
import pydicom
import traceback
import requests
import dicom2nifti
import requests.packages.urllib3
requests.packages.urllib3.disable_warnings
import os
import json
import glob 
import sys
import time 
import numpy as np
import zipfile
import pprint
import shutil 
import tempfile
from vistarsier import *
import nibabel as nib

def cleanServer(server):
    server.strip()
    if server[-1] == '/':
        server = server[:-1]
    if server.find('http') == -1:
        server = 'https://' + server
    return server
def isTrue(arg):
    return arg is not None and (arg == 'Y' or arg == '1' or arg == 'True')
def download(sess, name, pathDict):
    if os.access(pathDict['absolutePath'], os.R_OK):
        try:
            os.symlink(pathDict['absolutePath'], name)
        except:
            fileCopy(pathDict['absolutePath'], name)
            print ('Copied %s.' % pathDict['absolutePath'])
    else:
        with open(name, 'wb') as f:
            r = get(sess, pathDict['URI'], stream=True)
            for block in r.iter_content(1024):
                if not block:
                    break

                f.write(block)

def zipdir(dirPath=None, zipFilePath=None, includeDirInZip=True):
    if not zipFilePath:
        zipFilePath = dirPath + ".zip"
    if not os.path.isdir(dirPath):
        raise OSError("dirPath argument must point to a directory. "
            "'%s' does not." % dirPath)
    parentDir, dirToZip = os.path.split(dirPath)
    def trimPath(path):
        archivePath = path.replace(parentDir, "", 1)
        if parentDir:
            archivePath = archivePath.replace(os.path.sep, "", 1)
        if not includeDirInZip:
            archivePath = archivePath.replace(dirToZip + os.path.sep, "", 1)
        return os.path.normcase(archivePath)
    outFile = zipfile.ZipFile(zipFilePath, "w",
        compression=zipfile.ZIP_DEFLATED)
    for (archiveDirPath, dirNames, fileNames) in os.walk(dirPath):
        for fileName in fileNames:
            filePath = os.path.join(archiveDirPath, fileName)
            outFile.write(filePath, trimPath(filePath))
        # Make sure we get empty directories as well
        if not fileNames and not dirNames:
            zipInfo = zipfile.ZipInfo(trimPath(archiveDirPath) + "/")
            # some web sites suggest doing
            # zipInfo.external_attr = 16
            # or
            # zipInfo.external_attr = 48
            # Here to allow for inserting an empty directory.  Still TBD/TODO.
            outFile.writestr(zipInfo, "")
    outFile.close()
def get(sess, url, **kwargs):
    try:
        r = sess.get(url, **kwargs)
        r.raise_for_status()
    except (requests.ConnectionError, requests.exceptions.RequestException) as e:
        print ("Request Failed")
        print ("    " + str(e))
        sys.exit(1)
    return r  
def get_frames(sess, host, experiment_id, scan_id):
    r = get(sess, host+ "/data/experiments/%s/scans/%s" % (experiment_id, scan_id), params={"format":"json"})
    return r.json()['items'][0]['data_fields']['frames']
    
def identify_scan(sess, host, session_id):
    # Get list of scan ids
    print ("Get scan list for session ID %s." % session_id)
    r = get(sess, host + "/data/experiments/%s/scans" % session_id, params={"format": "json"})
    scanRequestResultList = r.json()["ResultSet"]["Result"]
    scanIDList = sorted([(scan['ID'],scan['series_description'],int(get_frames(sess, host, session_id, scan['ID']))) for scan in scanRequestResultList if 'flair' in scan['series_description'].lower() and 'spc' in scan['series_description'].lower()], key=lambda x:-x[2])    
    print ('Found scans ',scanIDList)
    print ('Choosing', scanIDList[0])
    return scanIDList[0][0]

def download_series(sess, host, session_id, scan_id, output_dir):
    # Deal with DICOMs
    print ('Get list of DICOM files for scan %s.' % scan_id)
    filesURL = host + "/data/experiments/%s/scans/%s/resources/DICOM/files" % (session_id, scan_id)
    print (filesURL)

    r = get(sess, filesURL, params={"format": "json"})
    # I don't like the results being in a list, so I will build a dict keyed off file name
    dicomFileDict = {dicom['Name']: {'URI': host + dicom['URI']} for dicom in r.json()["ResultSet"]["Result"]}

    # Have to manually add absolutePath with a separate request
    r = get(sess, filesURL, params={"format": "json", "locator": "absolutePath"})
    for dicom in r.json()["ResultSet"]["Result"]:
        dicomFileDict[dicom['Name']]['absolutePath'] = dicom['absolutePath']

    ##########
    # Download DICOMs
    os.chdir(output_dir)

    # Check secondary
    # Download any one DICOM from the series and check its headers
    # If the headers indicate it is a secondary capture, we will skip this series.
    dicomFileList = dicomFileDict.items()

    ##########
    for name, pathDict in dicomFileList:
        download(sess, name, pathDict)

    print ('Done downloading for scan %s.' % scan_id)
def map_output(output_np_array, dses, output_folder, addition, uid_addition):
    assert len(output_np_array.shape) == 4
    assert output_np_array.shape[2] == len(dses)
    for i, ds in enumerate(dses):
        ds.PhotometricInterpretation = 'RGB'
        ds.SamplesPerPixel = 3
        ds.PlanarConfiguration = 0 
        ds.PixelData = output_np_array[:,:,i,:].astype(np.uint8).transpose((1,0,2)).tobytes() 
        ds.Rows = output_np_array.shape[1]
        ds.Columns = output_np_array.shape[0]
        ds.BitsAllocated = 8
        ds.BitsStored = 8
        ds.HighBit = 7
        ds.PixelRepresentation = 0
        ds.SeriesNumber = str(ds.SeriesNumber) + uid_addition
        ds.SeriesDescription += addition
        ds.SeriesInstanceUID += '.'+uid_addition
        ds.SOPInstanceUID += '.'+uid_addition
        ds.save_as(os.path.join(output_folder, str(i)+'.dcm'), write_like_original=False)
def upload_dir(sess, host, upload_dir, project, subjectID, session, scanid, workflowId, uploadByRef, series_description, series_uid):
    #time.sleep(0.5)
    print ('Uploading files for scan %s' % scanid)
    queryArgs = {"format": "DICOM", "content": "DICOM"}
    try:
        r = sess.put(host + '/data/projects/%s/subjects/%s/experiments/%s/scans/%s' % (project, subjectID, session, scanid), params={'xsiType':'xnat:mrScanData',
                        'series_description':series_description,
                        'type':series_description,
                        'quality':'usable',
                        'frames':len(os.listdir(upload_dir)),
                        'ID':scanid,
                        'UID':series_uid,
                        'modality':'MR'})
        r.raise_for_status()
    except:
        print (traceback.format_exc())
    
    if workflowId is not None:
        queryArgs["event_id"] = workflowId
    if uploadByRef:
        queryArgs["reference"] = os.path.abspath(upload_dir)
        r = sess.put(host + "/data/experiments/%s/scans/%s/resources/DICOM/files" % (session, scanid), params=queryArgs)
        r.raise_for_status()
    else:
        queryArgs["extract"] = True
        queryArgs["overwrite"] = True
        (t, tempFilePath) = tempfile.mkstemp(suffix='.zip')
        zipdir(dirPath=os.path.abspath(upload_dir), zipFilePath=tempFilePath, includeDirInZip=False)
        files = {'file': open(tempFilePath, 'rb')}
        r = sess.post(host + "/data/experiments/%s/scans/%s/resources/DICOM/files" % (session, scanid), params=queryArgs, files=files)
        r.raise_for_status()
        os.remove(tempFilePath)  

def get_experiment_details(sess, host, project, id):
    if 'XNAT' in id:  # if its an experiment-id then you don't need the project
        print ("Get project and subject ID for session ID %s." % id)
        r = get(sess, host + "/data/experiments/%s" % id, params={"format": "json", "handler": "values", "columns": "project,subject_ID,ID"})
        sessionValuesJson = r.json()["ResultSet"]["Result"][0]
        project = sessionValuesJson["project"]
        subjectID = sessionValuesJson["subject_ID"]
        print ("Project: " + project)
        print ("Subject ID: " + subjectID)
    else:
        print ("Get subject ID for session ID %s." % id)
        r = get(sess, host + "/data/projects/%s/experiments/%s" % (project,id), params={"format": "json", "handler": "values", "columns": "project,subject_ID,ID"})
        sessionValuesJson = r.json()["ResultSet"]["Result"][0]
        subjectID = sessionValuesJson["subject_ID"]
        id  = sessionValuesJson["ID"]
        print ("Subject ID: " + subjectID)
        print ("Experiment ID: " + id)
    return project, subjectID, id

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run pytarsier on session")
    parser.add_argument("--host", default="http://ahmldicom01.baysidehealth.intra", help="XNAT host")
    parser.add_argument("--user", help="XNAT username", required=True)
    parser.add_argument("--password", help="Password", required=True)
    parser.add_argument("--fixed_session_id", help="Fixed Session ID", required=True)
    parser.add_argument("--fixed_scan_id", help="Fixed Scan ID", required=False)
    parser.add_argument("--floating_session_id", help="Floating Session ID", required=True)
    parser.add_argument("--floating_scan_id", help="Floating Scan ID", required=False)
    parser.add_argument("--project", help="Project", default='Alfred')
    parser.add_argument("--dicomdir", help="Root output directory for DICOM files", required=True)
    parser.add_argument("--upload-by-ref", help="Upload \"by reference\". Only use if your host can read your file system.")
    parser.add_argument("--workflowId", help="Pipeline workflow ID")

    args, unknown_args = parser.parse_known_args()
    print (args)
    fixed_session_id = args.fixed_session_id
    fixed_scan_id = args.fixed_scan_id
    if fixed_scan_id == 'None': fixed_scan_id = None
    floating_session_id = args.floating_session_id
    floating_scan_id = args.floating_scan_id
    if floating_scan_id == 'None': floating_scan_id = None
    workflowId = args.workflowId
    project = args.project
    uploadByRef = isTrue(args.upload_by_ref)
    host = cleanServer(args.host)
    dicomdir = args.dicomdir
    outputincdir = dicomdir+'/output-inc'
    outputdecdir = dicomdir+'/output-dec'
    builddir = os.getcwd()
    # Set up session
    sess = requests.Session()
    sess.verify = False
    sess.auth = (args.user, args.password)
    
    project1, subjectID1, fixed_session_id = get_experiment_details(sess, host, project, fixed_session_id)
    project2, subjectID2, floating_session_id = get_experiment_details(sess, host, project, floating_session_id)
    
    assert subjectID1 == subjectID2
    subjectID = subjectID1
    assert project1 == project2 
    project = project1
    
    # Set up working directory
    if not os.access(dicomdir, os.R_OK):
        print ('Making DICOM directory %s' % dicomdir)
        os.mkdir(dicomdir)
    # Set up working directory
    if not os.access(outputincdir, os.R_OK):
        print ('Making output DICOM directory %s' % outputincdir)
        os.mkdir(outputincdir)
    # Set up working directory
    if not os.access(outputdecdir, os.R_OK):
        print ('Making output DICOM directory %s' % outputdecdir)
        os.mkdir(outputdecdir)
    
    
    if fixed_scan_id is None:
        print ('Fixed scan id is none, trying to identify ...')
        fixed_scan_id = identify_scan(sess, host, fixed_session_id)
    if floating_scan_id is None:
        print ('Floating scan id is none, trying to identify ...')
        floating_scan_id = identify_scan(sess, host, floating_session_id)
    
    fixed_dicom_dir = os.path.join(dicomdir, 'fixed')
    if not os.path.isdir(fixed_dicom_dir):
        print ('Making fixed DICOM directory %s.' % fixed_dicom_dir)
        os.mkdir(fixed_dicom_dir)
        
    floating_dicom_dir = os.path.join(dicomdir, 'floating')
    if not os.path.isdir(floating_dicom_dir):
        print ('Making floating DICOM directory %s.' % floating_dicom_dir)
        os.mkdir(floating_dicom_dir)
        
    for f in os.listdir(fixed_dicom_dir):
        os.remove(os.path.join(fixed_dicom_dir, f))
    for f in os.listdir(floating_dicom_dir):
        os.remove(os.path.join(floating_dicom_dir, f))
    for f in os.listdir(outputincdir):
        os.remove(os.path.join(outputincdir, f))
    for f in os.listdir(outputdecdir):
        os.remove(os.path.join(outputdecdir, f))
    
    download_series(sess, host, fixed_session_id, fixed_scan_id, fixed_dicom_dir)
    download_series(sess, host, floating_session_id, floating_scan_id, floating_dicom_dir)
    
    fixed_nifti = os.path.join(dicomdir, 'fixed.nii')
    floating_nifti = os.path.join(dicomdir, 'floating.nii')
    os.chdir(dicomdir)
    dicom2nifti.dicom_series_to_nifti(fixed_dicom_dir, fixed_nifti, reorient_nifti=False)
    dicom2nifti.dicom_series_to_nifti(floating_dicom_dir, floating_nifti, reorient_nifti=False)
    
    # Run biascorrection | skull stripping | registration
    prior_proc, current_proc = pre_process(floating_nifti, fixed_nifti)
        
    # Load pre-processed images
    pimg = nib.load(prior_proc)
    cimg = nib.load(current_proc)
    # Calculate change
    change = vistarsier_compare(cimg.get_fdata(), pimg.get_fdata())
    # Apply colourmaps
    print('Applying colormaps...')
    inc_output, dec_output = display_change(cimg.get_fdata(), change)
    
    comparison_date = pydicom.read_file(os.path.join(floating_dicom_dir,os.listdir(floating_dicom_dir)[0])).StudyDate
    dses = [pydicom.dcmread(open(os.path.join(fixed_dicom_dir,f),'rb')) for f in sorted(os.listdir(fixed_dicom_dir), key=lambda x:-int(x.split('-')[-2]) )]
    
    map_output(inc_output, dses, outputincdir, '-'+comparison_date+'-inc', '000'+comparison_date)
    
    dses = [pydicom.dcmread(open(os.path.join(fixed_dicom_dir,f),'rb')) for f in sorted(os.listdir(fixed_dicom_dir), key=lambda x:-int(x.split('-')[-2]) )]
    
    map_output(dec_output, dses, outputdecdir, '-'+comparison_date+'-dec', '100'+comparison_date)
    print (inc_output.shape, dec_output.shape, len(dses), dses[0].pixel_array.shape)
        
    print ('upload increased')
    series_description = pydicom.read_file(os.path.join(outputincdir, '0.dcm')).SeriesDescription
    series_uid = pydicom.read_file(os.path.join(outputincdir, '0.dcm')).SeriesInstanceUID    
    upload_dir(sess, host, outputincdir, project, subjectID, fixed_session_id, fixed_scan_id+'000'+comparison_date, workflowId, uploadByRef, series_description, series_uid)
    print ('upload decreased')
    series_description = pydicom.read_file(os.path.join(outputdecdir, '0.dcm')).SeriesDescription
    series_uid = pydicom.read_file(os.path.join(outputdecdir, '0.dcm')).SeriesInstanceUID   
    upload_dir(sess, host, outputdecdir, project, subjectID, fixed_session_id, fixed_scan_id+'100'+comparison_date, workflowId, uploadByRef, series_description, series_uid)
    print('...ALL DONE!')
    
    r=sess.post(host+'/xapi/viewer/projects/'+project+'/experiments/'+fixed_session_id, data={})
    r.raise_for_status()
    