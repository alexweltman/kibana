#!/usr/bin/python
import os
import sys
import argparse
import json
from util import ElasticsearchUtil
from util import Logger
from util import Utility

EXPORT_LOG = "/tmp/ExportAssets.log"

esUtil = ElasticsearchUtil(EXPORT_LOG)
logger = Logger(log_file=EXPORT_LOG)
logging, rotating_handler = logger.configure_and_return_logging()
UTIL = Utility(log_file=EXPORT_LOG)

OUTPUT_DIR = os.path.dirname(os.path.realpath(__file__)) 

INDEX = esUtil.KIBANA_INDEX
TYPE = None
ID = None

DASHBOARD = "dashboard"
VISUALIZATION = "visualization"
SEARCH = "search"

FILE_PATHS_AND_CONTENTS = {}


def get_asset(es_index, es_type, es_id):
   ignored, doc_exists = esUtil.function_with_timeout(esUtil.ES_QUERY_TIMEOUT,
                                           esUtil.document_exists,
                                             es_index,
                                             es_type,
                                             es_id)
   if doc_exists:
      success, ret = esUtil.get_document(es_index, es_type, es_id)
      logging.info("GET RETURNS: " + "\n" + UTIL.pretty_format(ret))
      return True, ret
   else:
      logging.info("No such thing as " + es_id + " in /" + es_index + "/" + es_type + "/")
      return False, "Not found"

def print_error_and_usage(argParser, error):
   print "Error:  " + error + "\n"
   print argParser.print_help()
   sys.exit(2)

def santize_input_args(arg_parser, args):
   if len(sys.argv) == 1:
      print_error_and_usage(argParser, "No arguments supplied.")
   if (args.dash_name is None
      and args.viz_name is None
      and args.search_name is None):
      print_error_and_usage(argParser, "Must have one of the following flags: -d -v -s")

def get_filename(asset_title):
   return asset_title + ".json"

def get_full_path(asset_id):
   global OUTPUT_DIR
   if OUTPUT_DIR[-1] == '/':
      return OUTPUT_DIR + get_filename(asset_id)
   else:
      return OUTPUT_DIR + "/" + get_filename(asset_id)

def strip_metadata(json_string):
   ob = json.loads(json.dumps(json_string))
   return UTIL.safe_list_read(list_ob=ob, key='_source')

def get_dashboard_panels(panels_str):
   panels_with_type = {}
   db_panels_json = json.loads(UTIL.remove_all_char(string=panels_str, to_remove="\\"))
   for index, panel in enumerate(db_panels_json):
      
      panel_id = UTIL.safe_list_read(list_ob=db_panels_json[index], key='id')
      panel_type = UTIL.safe_list_read(list_ob=db_panels_json[index], key='type')
      panels_with_type[panel_id] = panel_type
   return panels_with_type

def export_all_files(asset_dict=FILE_PATHS_AND_CONTENTS):
   global OUTPUT_DIR
   for asset_name, asset_content in asset_dict.iteritems():
      UTIL.print_to_file(asset_content, asset_name)

def get_all_dashboard_content_from_ES(dashboard_raw):
   global FILE_PATHS_AND_CONTENTS
   global INDEX
   db_json = UTIL.make_json(dashboard_raw)
   db_panels_raw = UTIL.safe_list_read(list_ob=db_json, key='panelsJSON')
   panels_with_type = get_dashboard_panels(db_panels_raw)
   for panel_id, panel_type in panels_with_type.iteritems():
      success, ret = get_asset(INDEX, panel_type, panel_id)
      if success:
         FILE_PATHS_AND_CONTENTS[get_full_path(panel_id)] = strip_metadata(ret)
      else:
         print "ERROR: Failed to get asset " + panel_id + " needed by dashboard."

def add_asset_to_output_dict(asset_raw, asset_id):
   global FILE_PATHS_AND_CONTENTS
   asset_raw_no_meta = strip_metadata(json_string=asset_raw)
   full_file_path = get_full_path(asset_id=asset_id)
   FILE_PATHS_AND_CONTENTS[full_file_path] = asset_raw_no_meta


# ----------------- MAIN -----------------
def main(argv):

   argParser = argparse.ArgumentParser(description="Export dashboards, visualizations, or searches from Elasticsearch")
   argParser.add_argument("-d", "--dashboard", dest="dash_name", metavar="DASHBOARD_NAME", help="Export dashboard and all of its assets")
   argParser.add_argument("-v", "--visualization", dest="viz_name", metavar="VIZUALIZATION_NAME", help="Export a single visualization")
   argParser.add_argument("-s", "--search", dest="search_name", metavar="SEARCH_NAME", help="Export a single search")
   argParser.add_argument("-o", "--outputdir", dest="directory", metavar="DIR_NAME", help="Specify an output directory for the exported file")
   
   args = argParser.parse_args()

   santize_input_args(arg_parser=argParser, args=args)
   
   global OUTPUT_DIR
   global FILE_PATHS_AND_CONTENTS
   global TYPE
   global ID

   if args.dash_name:
      TYPE = DASHBOARD
      ID = args.dash_name
   elif args.viz_name:
      TYPE = VISUALIZATION
      ID = args.viz_name
   elif args.search_name:
      TYPE = SEARCH
      ID = args.search_name

   if args.directory:
      OUTPUT_DIR = args.directory

   success, asset_raw = get_asset(es_index=INDEX, es_type=TYPE, es_id=ID)


   if success:
      add_asset_to_output_dict(asset_raw=asset_raw, asset_id=ID)
      if TYPE == DASHBOARD:
         get_all_dashboard_content_from_ES(dashboard_raw=UTIL.safe_list_read(list_ob=FILE_PATHS_AND_CONTENTS, key=get_full_path(asset_id=ID)))
      export_all_files()
   else:
      print "ERROR:   Did not find any " + TYPE + " named " + ID + " in Elasticsearch."
      sys.exit(2)


if __name__ == '__main__':
    main(sys.argv[1:])