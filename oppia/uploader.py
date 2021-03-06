# oppia/uploader.py
import json
import shutil
import xml.dom.minidom
import zipfile
from xml.dom.minidom import Node

import os
from django.conf import settings
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from oppia.models import Course, Section, Activity, Media


def handle_uploaded_file(f, extract_path, request, user):
    zipfilepath = settings.COURSE_UPLOAD_DIR + f.name
    
    with open(zipfilepath, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)
            
    zip = zipfile.ZipFile(zipfilepath)
    zip.extractall(path=extract_path)      
    
    mod_name = ''
    for dir in os.listdir(extract_path)[:1]:
        mod_name = dir
       
    # check there is at least a sub dir 
    if mod_name == '':
        messages.info(request, _("Invalid course zip file"))
        return False
    
    # check that the 
    if not os.path.isfile(os.path.join(extract_path, mod_name, "module.xml")):
        messages.info(request, _("Zip file does not contain a module.xml file"))
        return False
      
    # parse the module.xml file
    print extract_path
    print mod_name
    
    doc = xml.dom.minidom.parse(os.path.join(extract_path, mod_name, "module.xml")) 
    for meta in doc.getElementsByTagName("meta")[:1]:
        versionid = 0
        for v in meta.getElementsByTagName("versionid")[:1]:
            versionid = int(v.firstChild.nodeValue)
        temp_title = {}
        for t in meta.childNodes:
            if t.nodeName == "title":
                temp_title[t.getAttribute('lang')] = t.firstChild.nodeValue
        title = json.dumps(temp_title)
        
        temp_description = {}
        for t in meta.childNodes:
            if t.nodeName == "description":
                if t.firstChild is not None:
                    temp_description[t.getAttribute('lang')] = t.firstChild.nodeValue
                else:
                    temp_description[t.getAttribute('lang')] = None
        description = json.dumps(temp_description)
        
        shortname = ''
        for sn in meta.getElementsByTagName("shortname")[:1]:
            shortname = sn.firstChild.nodeValue
    
    old_course_filename = None
    # Find if course already exists
    try: 
        
        print shortname
        
        course = Course.objects.get(shortname=shortname)
        old_course_filename = course.filename

        # check that the current user is allowed to wipe out the other course
        if course.user != user:
            messages.info(request, _("Sorry, only the original owner may update this course"))
            return False
        
        # check if course version is older
        if course.version > versionid:
            messages.info(request, _("A newer version of this course already exists"))
            return False
        # wipe out the old sections/activities/media
        oldsections = Section.objects.filter(course=course)
        oldsections.delete()
        oldmedia = Media.objects.filter(course=course)
        oldmedia.delete()
        
        course.shortname = shortname
        course.title = title
        course.description = description
        course.version = versionid
        course.user = user
        course.filename = f.name
        course.lastupdated_date = timezone.now()
        course.save()
    except Course.DoesNotExist:
        course = Course()
        course.shortname = shortname
        course.title = title
        course.description = description
        course.version = versionid
        course.user = user
        course.filename = f.name
        course.is_draft = True
        course.save()
       
    # add in any baseline activities
    for meta in doc.getElementsByTagName("meta")[:1]:
        if meta.getElementsByTagName("activity").length > 0:
            section = Section()
            section.course = course
            section.title = '{"en": "Baseline"}'
            section.order = 0
            section.save()
            for a in meta.getElementsByTagName("activity"):
                parse_and_save_activity(section, a, True)
                    
    # add all the sections
    for structure in doc.getElementsByTagName("structure")[:1]:
        
        if structure.getElementsByTagName("section").length == 0:
            messages.info(request, _("There don't appear to be any activities in this upload file."))
            course.delete()
            return False
        
        for s in structure.getElementsByTagName("section"):
            temp_title = {}
            for t in s.childNodes:
                if t.nodeName == 'title':
                    temp_title[t.getAttribute('lang')] = t.firstChild.nodeValue
            title = json.dumps(temp_title)
            section = Section()
            section.course = course
            section.title = title
            section.order = s.getAttribute("order")
            section.save()
            
            # add all the activities
            for activities in s.getElementsByTagName("activities")[:1]:
                for a in activities.getElementsByTagName("activity"):
                    parse_and_save_activity(section, a, False)
                    
    # add all the media
    for file in doc.lastChild.lastChild.childNodes:
        if file.nodeName == 'file':
            media = Media()
            media.course = course
            media.filename = file.getAttribute("filename")
            media.download_url = file.getAttribute("download_url")
            media.digest = file.getAttribute("digest")
            
            # get any optional attributes
            for attrName, attrValue in file.attributes.items():
                if attrName == "length":
                    media.media_length = attrValue
                if attrName == "filesize":
                    media.filesize = attrValue

            media.save()
    
    if old_course_filename is not None and old_course_filename != course.filename:
        try:
            os.remove(settings.COURSE_UPLOAD_DIR + old_course_filename)
        except OSError:
            pass
    
    # Extract the final file into the courses area for preview
    zipfilepath = settings.COURSE_UPLOAD_DIR + f.name
    
    with open(zipfilepath, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)
            
    zip = zipfile.ZipFile(zipfilepath)
    course_preview_path = settings.MEDIA_ROOT + "courses/"
    zip.extractall(path=course_preview_path)      
    
    # remove the temp upload files
    shutil.rmtree(extract_path, ignore_errors=True)
        
    return course       


def parse_and_save_activity(section, act, is_baseline=False):
    """
    Parses an Activity XML and saves it to the DB
    :param section: section the activity belongs to
    :param act: a XML DOM element containing a single activity
    :param is_baseline: is the activity part of the baseline?
    :return: None
    """
    temp_title = {}
    for t in act.getElementsByTagName("title"):
        temp_title[t.getAttribute('lang')] = t.firstChild.nodeValue
    title = json.dumps(temp_title)

    content = ""
    if act.getAttribute("type") == "page":
        temp_content = {}
        for t in act.getElementsByTagName("location"):
            if t.firstChild and t.getAttribute('lang'):
                temp_content[t.getAttribute('lang')] = t.firstChild.nodeValue
        content = json.dumps(temp_content)
    elif act.getAttribute("type") == "quiz":
        for c in act.getElementsByTagName("content"):
            content = c.firstChild.nodeValue
    elif act.getAttribute("type") == "feedback":
        for c in act.getElementsByTagName("content"):
            content = c.firstChild.nodeValue
    elif act.getAttribute("type") == "resource":
        for c in act.getElementsByTagName("location"):
            content = c.firstChild.nodeValue
    elif act.getAttribute("type") == "url":
        temp_content = {}
        for t in act.getElementsByTagName("location"):
            if t.firstChild and t.getAttribute('lang'):
                temp_content[t.getAttribute('lang')] = t.firstChild.nodeValue
        content = json.dumps(temp_content)
    else:
        content = None
    
    image = None
    if act.getElementsByTagName("image"):
        for i in act.getElementsByTagName("image"):
            image = i.getAttribute('filename') 

    if act.getElementsByTagName("description"):
        description = {}
        for d in act.getElementsByTagName("description"):
            if d.firstChild and d.getAttribute('lang'):
                description[d.getAttribute('lang')] = d.firstChild.nodeValue
        description = json.dumps(description)
    else:
        description = None
          
    activity = Activity()
    activity.section = section
    activity.order = act.getAttribute("order")
    activity.title = title
    activity.type = act.getAttribute("type")
    activity.digest = act.getAttribute("digest")
    activity.baseline = is_baseline
    activity.image = image
    activity.content = content
    activity.description = description
    activity.save()           