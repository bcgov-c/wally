#!/bin/bash

# USAGE: ./wfs_direct_download.sh <wally database table name>
# 
# Sort key is needed for WFS pagination, which is likely required except for small (<10000 features) datasets,
# and will be looked up from the metadata.data_source table.
#
# This script will download data from DataBC WMS, using multiple requests if necessary, and upload it to an
# S3 compatible storage (see line 66 for s3 config).

set -e

cd /dataload


row = $(psql -t "postgres://wally:$POSTGRES_PASSWORD@$POSTGRES_SERVER:5432/wally" -c "select ds.source_object_name, ds.source_object_id FROM metadata.data_source WHERE data_table_name='$1';")

DATABC_LAYER_NAME=row[0]
SORT_KEY=row[1]
WALLY_LAYER_NAME=$1

[ -z "$DATABC_LAYER_NAME" ] && echo "No layer name provided. \nUsage: ./wfs_direct_download.sh <DATABC_LAYER_NAME> <sort_key> <wally_layer_name>" && exit 1
[ -z "$SORT_KEY" ] && echo "No sort key provided (required by WFS). \nUsage: ./wfs_direct_download.sh <DATABC_LAYER_NAME> <sort_key> <wally_layer_name>" && exit 1
[ -z "$WALLY_LAYER_NAME" ] && echo "No internal layer name provided. \nUsage: ./wfs_direct_download.sh <DATABC_LAYER_NAME> <sort_key> <wally_layer_name>" && exit 1

index=0
downloaded=0

# make a temp dir
mkdir -p "./.$DATABC_LAYER_NAME"


# download from the 
echo "Making request starting at $index"
curl -s -o "./.$DATABC_LAYER_NAME/$index.geojson" "https://openmaps.gov.bc.ca/geo/pub/wfs?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&outputFormat=json&typeNames=$DATABC_LAYER_NAME&count=10000&startIndex=$downloaded&sortBy=$SORT_KEY"
matched=$(jq '.numberMatched' "./.$DATABC_LAYER_NAME/$index.geojson")
retrieved=$(jq '.numberReturned' "./.$DATABC_LAYER_NAME/$index.geojson")
let downloaded=downloaded+retrieved


while [ $downloaded -lt $matched ]
do
  ((index++)) && ((index==20)) && echo "Exceeded loop limit ($index) without retrieving all files, stopping. There are $matched records, but only $downloaded were retrieved." && exit 1

  echo "$downloaded downloaded, $matched total.  Making another request ..."

  sleep 3
  curl -s -o "./.$DATABC_LAYER_NAME/$index.geojson" "https://openmaps.gov.bc.ca/geo/pub/wfs?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&outputFormat=json&typeNames=$DATABC_LAYER_NAME&count=10000&startIndex=$downloaded&sortBy=$SORT_KEY"
  retrieved_this_iter=$(jq '.numberReturned' "./.$DATABC_LAYER_NAME/$index.geojson")
  let downloaded=downloaded+retrieved_this_iter
  
done
echo "Downloaded $downloaded of $matched."
echo "Combining files..."

mkdir -p ./out

for filename in $(ls ./.$DATABC_LAYER_NAME/*.geojson); do
    echo "merging" $filename
    [ -e "$filename" ] || continue
        ogr2ogr -f "GeoJSON" -update -append "./out/$DATABC_LAYER_NAME.geojson" "$filename" -nln "$DATABC_LAYER_NAME"
done

echo "Cleaning up..."
rm -r "./.$DATABC_LAYER_NAME"

echo "Zipping layer $DATABC_LAYER_NAME into $WALLY_LAYER_NAME.zip"
zip "./out/$WALLY_LAYER_NAME.zip" "./out/$DATABC_LAYER_NAME.geojson"

echo "Copying zipped layer to Minio storage..."
./mc --config-dir=./.mc config host add minio http://minio:9000 "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY"
./mc --config-dir=./.mc cp "./out/$WALLY_LAYER_NAME.zip" "minio/geojson"

rm "./out/$DATABC_LAYER_NAME.geojson"
rm "./out/$WALLY_LAYER_NAME.zip"

echo "Finished."
