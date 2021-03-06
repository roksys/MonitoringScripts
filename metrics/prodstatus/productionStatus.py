#!/usr/bin/python

''''
This script calculates the Production status of a site based on 
    - Downtimes: If a site has a declared downtime in the next 24h that is longer than 24h it'll be drained
    - Waiting Room / Morgue : If a site is in the waiting room or morgue, or any state not 'OK' it'll be set on drain
    - Manual override : If a site is overriden to any status [drain, down, on] it'll get this value
    - Site Readiness :  If a site was on drain 0.66 T of bad readiness on a 72 hour readiness value, it'll be marked on drain.
                        If a site is on drain and has >48 h days of good SR, it'll be out of drain

Inputs: Starting Timestamp in format "YYYY-mm-dd-hh-mm", Directory in which to output data
Output: Text file in current directory, named Hammercloud.txt

'''

from lib import dashboard, sites, url 
from datetime import datetime, timedelta
import os
import dateutil.parser
import json
from optparse import OptionParser
import sys

# Reads a metric from SS1B
def getJSONMetric(metricNumber, hoursToRead, sitesStr, sitesVar, dateStart="2000-01-01", dateEnd=datetime.now().strftime('%Y-%m-%d')):
    urlstr = "http://dashb-ssb.cern.ch/dashboard/request.py/getplotdata?columnid=" + str(metricNumber) + "&time=" + str(hoursToRead) + "&dateFrom=" + dateStart + "&dateTo=" + dateEnd + "&site=" + sitesStr + "&sites=" + sitesVar + "&clouds=all&batch=1"
    try:
        metricData = url.read(urlstr)
        return dashboard.parseJSONMetric(metricData)
    except:
        return None

def getJSONMetricforSite(metricNumber, hoursToRead, sitesStr):
    return getJSONMetric(metricNumber, hoursToRead, sitesStr, "one")

def getJSONMetricforAllSitesForDate(metricNumber, dateStart, dateEnd):
    return getJSONMetric(metricNumber, "custom", "", "all", dateStart, dateEnd)

# Filters a dashboard metric between times
def filterMetric(metric, dateStart, dateEnd):
    resultDict = {}
    if metric is not None:
        if metric.iteritems() != None:
            for key, value in metric.iteritems():
                metricEndTime = datetime.fromtimestamp(float(key))
                metricStartTime = datetime.fromtimestamp(float(value.date))
                bool1 = dateStart > metricStartTime
                bool2 = metricStartTime < metricEndTime
                bool3 = metricEndTime > dateEnd
                if ( bool1 and bool2 and bool3) :
                    resultDict[key] = value
    return resultDict

def formatDate(datetoFormat):
    return datetoFormat.strftime("%Y-%m-%d")
print '1'


def timedelta_total_seconds(timedelta):
    try:
        return (
        timedelta.microseconds + 0.0 +
        (timedelta.seconds + timedelta.days * 24 * 3600) * 10 ** 6) / 10 ** 6
    except:
        return 0 

def secondsofIntersection(t1start, t1end, t2start, t2end):
    latest_start = max(t1start, t2start)
    earliest_end = min(t1end, t2end)
    intersection = max(timedelta_total_seconds(earliest_end - latest_start),0)
    return intersection
#Contants 
OUTPUT_P_FILE_NAME = os.path.join(sys.argv[1],"primalProdStatus.txt")
COLORS = {}
DRAIN_STATUS = 'drain'
COLORS[DRAIN_STATUS] = 'yellow'

DOWN_STATUS = 'down'
COLORS[DOWN_STATUS] = 'red'

ON_STATUS = 'on'
COLORS[ON_STATUS] = 'green'

TIER0_STATUS = 'tier0'
COLORS[TIER0_STATUS] = 'green'

BAD_LIFESTATUS = ['Waiting_Room', 'Morgue']
DOWNTIMECOLOR = 'saddlebrown'
SITEREADINESS_OK = 'Ok'
SITEREADINESS_BAD = 'Error'


#Downtimes from last week to next year
downtimeStart = datetime.utcnow() - timedelta(weeks = 1)
downtimeEnd = datetime.utcnow() + timedelta(weeks = 1)
downtimes = getJSONMetricforAllSitesForDate(121, formatDate(downtimeStart),formatDate(downtimeEnd))
print'2'
#Site Readiness from last 3 days
srStart = datetime.utcnow() - timedelta(days = 3)
srEnd = datetime.utcnow() 
srStatus = getJSONMetricforAllSitesForDate(234, formatDate(srStart),formatDate(srEnd))
print '3'
#LifeStatus
lfStart = datetime.utcnow() - timedelta(days = 2)
lfEnd = datetime.utcnow() 
lfStatus = getJSONMetricforAllSitesForDate(235, formatDate(lfStart),formatDate(lfEnd))

#Current value prod_status
pdStart = datetime.utcnow() - timedelta(days = 1)
pdEnd = datetime.utcnow() 
pdStatus = getJSONMetricforAllSitesForDate(158, formatDate(pdStart),formatDate(pdEnd))

allsites = set(srStatus.getSites()).union(set(lfStatus.getSites())).union(set(downtimes.getSites()))

allsitesMetric = []
for site in allsites:
    tier = sites.getTier(site)
    siteCurrentLifeStatus = lfStatus.getLatestEntry(site)
    flagLifeStatus = False
    if siteCurrentLifeStatus is not None and (siteCurrentLifeStatus.value == 'Waiting_Room' or siteCurrentLifeStatus.value == 'Morgue'):
        flagLifeStatus = True
    siteSiteReadiness = srStatus.getSiteEntries(site)
    siteCurrentProd_Status = pdStatus.getLatestEntry(site) 
    siteDowntimes = downtimes.getSiteEntries(site)
    if tier == 2 or tier ==1: 
        #Check if the site will be on downtime in 24 hours or is on downtime 
        flagDowntime = False
        for key, value in siteDowntimes.iteritems():
            if value.color == 'saddlebrown':
                dateEnd = datetime.utcfromtimestamp(key)
                dateStart = datetime.utcfromtimestamp(value.date)
                intersection = 0 
                if timedelta_total_seconds(dateEnd - dateStart) > 86400:
                    currenttime = datetime.utcnow()
                    twodays = currenttime + timedelta(days = 2)
                    latest_start = max(dateStart, currenttime)
                    earliest_end = min(dateEnd, twodays)
                    intersection = timedelta_total_seconds(earliest_end - latest_start)
                if intersection > 0:
                    flagDowntime = True
        #Check SR last 3 days
        siteSiteReadinessTotal = {}
        for key, value in siteSiteReadiness.iteritems():
            dateEnd = datetime.utcfromtimestamp(key)
            dateStart = datetime.utcfromtimestamp(value.date)
            status = value.value
            # last day 
            now = datetime.utcnow()
            yesterday = now - timedelta(days = 1)
            twodays = now - timedelta(days = 2)
            threedays = now - timedelta(days = 3)
            siteSiteReadinessTotal[status] = siteSiteReadinessTotal.get(status, 0 ) +secondsofIntersection(dateStart, dateEnd, yesterday, now)
            siteSiteReadinessTotal[status] = siteSiteReadinessTotal.get(status, 0 ) +secondsofIntersection(dateStart, dateEnd, twodays,yesterday)
            siteSiteReadinessTotal[status] = siteSiteReadinessTotal.get(status, 0 ) +secondsofIntersection(dateStart, dateEnd, threedays,twodays)
        totalseconds = 0
        for key, value in siteSiteReadinessTotal.iteritems():
            if key == 'Ok' or key == 'Error':
                totalseconds += value
        if totalseconds > 0 :
            readinessScore  = siteSiteReadinessTotal.get('Ok', 0.0) / totalseconds
        else:
            readinessScore = -1.0 
        #Logic to calculate new prod status
        newProdStatus = 'unknown'
        if siteCurrentProd_Status != None and siteCurrentProd_Status.value == 'tier0':
            newProdStatus = 'tier0'
        if siteCurrentProd_Status != None and siteCurrentProd_Status.value == 'down':
            newProdStatus = 'down'
        if siteCurrentProd_Status != None and siteCurrentProd_Status.value == 'on':
            if flagDowntime or flagLifeStatus:
                newProdStatus = 'drain'
            else:
                newProdStatus = 'on'
        if siteCurrentProd_Status != None and siteCurrentProd_Status.value == 'drain':
            if not flagDowntime and not flagLifeStatus and readinessScore > 0.6:
                newProdStatus = 'on'
            else:
                newProdStatus = 'drain'
        allsitesMetric.append(dashboard.entry(date = now.strftime("%Y-%m-%d %H:%M:%S"), name = site, value = newProdStatus, color = COLORS.get(newProdStatus, 'white'), url = 'https://cmst1.web.cern.ch/CMST1/SST/drain_log.txt'))

if len(allsitesMetric) > 1:
    outputFileP = open(OUTPUT_P_FILE_NAME, 'w')
    for site in allsitesMetric:
        outputFileP.write(str(site) + '\n')
    print "\n--Output written to %s" % OUTPUT_P_FILE_NAME
    outputFileP.close()
