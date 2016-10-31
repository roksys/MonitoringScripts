#!/bin/sh

echo "Pilot Startup Site Test"
echo "More information - https://twiki.cern.ch/twiki/bin/view/CMSPublic/PilotStartupSiteTest"

exit_code=0

echo "Discover CMSSSW"
./discover_CMSSW.sh
exit_code=$?
echo "Exit code: " $exit_code

if [ "$exit_code" -eq "0" ]; then
  echo "siteconf validation"
  /usr/bin/python export_siteconf_info.py
  exit_code=$?
  echo $exit_code
fi

#Check job status that will be reported to the dashboard
if [ "$exit_code" -eq "0" ]; then
	grid_status="succeeded"
else
	grid_status="failed"
fi

#Generating taskId and jobRange for dashboard
MAXJOB=1000
SITENAME="${GLIDEIN_CMSSite}"
#SITENAME="T2_UK_London_IC"
TIMENOW=`/bin/date '+%s'`
TIMEMOD=`echo "${TIMENOW} % 900" | /usr/bin/bc`
TIME15M=`echo "${TIMENOW} - ${TIMEMOD}" | /usr/bin/bc`

TASK="PSST_${SITENAME}_${TIME15M}"

MAC=`/sbin/ifconfig -a | grep -m 1 -o -E '([[:xdigit:]]{1,2}:){5}[[:xdigit:]]{1,2}' | sed 's/://g'`
echo $MAC
MAC10=`echo "ibase=16; ${MAC}" | /usr/bin/bc`
MACMOD=`echo "${MAC10} + ${TIMEMOD}" | /usr/bin/bc`
JOB=`echo "${MACMOD} % ${MAXJOB}" | /usr/bin/bc`
# fi

echo "Sending post job info to the dashboard"
echo $SITENAME $exit_code $grid_status $TASK $JOB
/usr/bin/python DashboardAPI.py $SITENAME $exit_code $grid_status $TASK $JOB

echo "exit code " $exit_code

#line for crab3 report
cmsRun -j FrameworkJobReport.xml -p PSet.py
