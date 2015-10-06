# Outputs a set of html pages with diagrams to show file count by time. One year per page
# links to file diectorys are given
#
# Basic function:
# walk start_directory
#     match paths to regex
#     if match then extract date and count file
# make a page to display the info
#
# Inputs needed: start_directory - the directory to decend.
#                regex - With named elements to extract date
#                name -  a simple lable for each counts page set
#
# The regular expression needs labled parameter matches for year, month and day
# like this (?P<year>\d{4})
# Short cut elements are avaliable to make the regex more readable.
# YYYY = (?P<year>\d{4})
# YY   = (?P<year2>\d{2})
# MM   = (?P<month>\d{2})
# DD   = (?P<day>\d{2})

import os
import re
import datetime
import shelve
import ConfigParser

__author__ = 'Sam Pepler'


class Count:
    """"Class to contain a cached count of the number of files in a directory by day."""

    def __init__(self, name, start_directory, pattern, exclude_dir_pat=None):
        self.name = name
        self.start_directory = start_directory
        if exclude_dir_pat:
            self.exclude_dir_pat = re.compile(exclude_dir_pat)
        self.pattern = pattern
        regex_pat = pattern.replace("YYYY", r'(?P<year>\d{4})')
        regex_pat = regex_pat.replace("YY", r'(?P<year2>\d{2})')
        regex_pat = regex_pat.replace("MM", r'(?P<month>\d{2})')
        regex_pat = regex_pat.replace("DD", r'(?P<day>\d{2})')
        print regex_pat
        self.regex = re.compile(regex_pat)
        self.mod = None
        self.count = {}

    def do_count(self):
        """Launch a file count."""
        # if we have not done this count before  or the count is to old then redo the count.
        if self.name in cache:
            # old version in cache file
            print "cache version of %s avaliable" % self.name 
            try:
                old_version = cache[self.name]
            except:
                # malformed pickle object.
                print "Bad count form pickled cache - redo anyway"
                old_version = None
            # if not to old then use cached results
            # print old_version.mod, redo_time, datetime.datetime.now()
            if old_version is not None and old_version.mod + redo_time > datetime.datetime.now():
                print "cache version new enough to use"
                self.count = old_version.count
                return

        print "Need to update the count"
        # set modifided time for count
        self.mod = datetime.datetime.now()

        print "find files..."
        for d, dirs, files in os.walk(start_directory, followlinks=True):
            # skip excluded directories
            print " In %s" % d
            if self.exclude_dir_pat:
                if self.exclude_dir_pat.search(d):
                    print "SKIP excluded dir"
                    continue
            for f in files:
                path = os.path.join(d, f)
                print "PATH %s" % path
                match = self.regex.search(path)
                if match:
                    matchdict = match.groupdict()
                    if "year" in matchdict:
                        year = int(matchdict["year"])
                    elif "year2" in matchdict:
                        year = int(matchdict["year2"])
                        if year > 40: year +=1900
                        else: year += 2000
                    month = int(matchdict["month"])
                    day = int(matchdict["day"])
                    if "group" in matchdict:
                        group = matchdict["group"]
                    else:
                        group = ""
                    print "%s > %s" % (path, group)
                    try:
                        date = datetime.date(year, month, day)
                    except ValueError:
                        print "BAD DATE"
                        continue
                    if group not in self.count:
                        self.count[group] = {}
                    if date in self.count[group]:
                        self.count[group][date] = (self.count[group][date][0]+ 1, d)
                    else:
                        self.count[group][date] = (1, d)
                    print ".",
                else:
                    print "%s - NO MATCH" % path    
        # store result in shelve db
        print "Storing %s..." % count_name
        cache[count_name] = self   # store data at key (overwrites old data if using an existing key)
        cache.close()
        print "Stored."

    def data_table(self):
        """Make a sorted data table for count values. Also returns year and group lists"""
        dates = []
        years = []
        groups = self.count.keys()
        for group in groups:
            for date in self.count[group].keys():
                if date not in dates:
                    dates.append(date)
                if date.year not in years:
                    years.append(date.year)
        years.sort()
        dates.sort()

        # Make table with lines on form (date, nfile_group1, nfiles_group2, ...)
        data = []
        urls = []
        for date in dates:
            table_line = [date]
            url_line = []
            for group in groups:
                if date in self.count[group]:
                    table_line.append(self.count[group][date][0])
                    url_line.append(self.count[group][date][1])
                else:
                    table_line.append(0)
                    url_line.append("")
            data.append(table_line)
            urls.append(url_line)
        return groups, years, data, urls

    # make html page
    def make_html(self):
        groups, years, data, urls = self.data_table()
        print groups, years

        # base url for data browser
        browser = "http://browse.ceda.ac.uk/browse/"

        for year in years:
            filename = "%s.%s.html" % (self.name, year)
            print filename
            html = open(filename, "w")

            html.write("<html>\n")
            html.write("""<head><script type="text/javascript" src="https://www.google.com/jsapi"></script></head>""")
            html.write("<body><h1>Count name:%s</h1>\n" % self.name)
            html.write("Regex: %s<br/>\n" % self.pattern)
            html.write("Directory: %s<br/>\n" % self.start_directory)

            # write year links to other files
            for syear in years:
                html.write('<a href="%s.%s.html">%s</a> | \n' % (self.name, syear, syear))

            # make data and urls tables - data table needs to fit google charts API
            data_table = "var rows = ["
            urls_data = "var urls = ["
            i = 0
            for row in data:
                date = row[0]
                row_urls = urls[i]
                i += 1
                if date.year != year:
                    continue
                values = ",".join(map(str, row[1:]))
                data_table += "[new Date(%s,%s,%s,12,0,0,0), %s]," % (date.year, date.month-1, date.day, values)
                urls_data += "%s, " % row_urls
            data_table += "];"
            urls_data += "];"

            # make google charts columns for each group
            columns = ""
            for group in groups:
                columns += "  data.addColumn('number', 'files %s');\n" % group

            # make google charts view window options to explicitly cover 1 year
            view_window = "viewWindow: {min: new Date(%s, 0, 1, 0, 0, 0, 0), max: new Date(%s, 0, 1, 0, 0, 0, 0)}, " % (year, year+1)

            html.write("""
        <script>
        %s     // Data for chart
        %s     // urls for links

          // Load the Visualization API and the piechart package.
          google.load('visualization', '1.0', {'packages':['corechart']});
          // Set a callback to run when the Google Visualization API is loaded.
          google.setOnLoadCallback(drawStacked);

          function drawStacked() {
              var data = new google.visualization.DataTable();
              data.addColumn('date', 'Date');
              %s    // adding columns

              data.addRows(rows);

              var options = {
                 title: 'Files over time',
                 isStacked: true,
                 vAxis: {title: 'Number of files'},
                 bar: {groupWidth: "4"},
                 height: 400,
                 legend: {position: 'top', textStyle: {color: 'blue', fontSize: 12}},
                 hAxis: {title: 'Date',
                         %s  // view window options
                        }
              };

              function selectHandler(e) {
                 // function to goto url from chart click
                 var  d = chart.getSelection()[0];
                 var  selection = urls[d.row][d.column-1];
                 window.location.assign("%s"+selection);
              };

          var chart = new google.visualization.ColumnChart(document.getElementById('chart_div'));
          google.visualization.events.addListener(chart, 'select', selectHandler);
          chart.draw(data, options);
        }

        </script>

        <!--Div that will hold the chart-->
        <div id="chart_div"></div>
      </body>
    </html>
          """ % (data_table, urls_data, columns, view_window, browser))
            html.close()


if __name__ == "__main__":
    config = ConfigParser.RawConfigParser()
    config.read('file_counter.cfg')
    count_names = config.sections()

    for count_name in count_names:
        cachefile = config.get(count_name, "cachefile")
        cache = shelve.open(cachefile)
        redo_time = config.getfloat(count_name, "redo_time")    # time in days
        metadata_dir = config.get(count_name, "metadata_dir")    # destination for the temporal coverage plots
        exclude_dir_pat = config.get(count_name, "exclude_dir_pat")    # directories matching this pattern are skipped
        redo_time = datetime.timedelta(days=redo_time)   # redo the count if not done in redo_time in seconds

        count_start_directory = config.get(count_name, "start_directory")
        count_regex_pat = config.get(count_name, "regex_pat")

        C = Count(count_name, count_start_directory, count_regex_pat, exclude_dir_pat)
        C.do_count()
        print "make html - %s " % count_name
        C.make_html()


