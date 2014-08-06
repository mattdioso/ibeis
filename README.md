# IBEIS
## I.B.E.I.S. = Image Based Ecological Information System
=====


Erotemic's IBEIS module dependencies 

* https://github.com/Erotemic/utool
* https://github.com/Erotemic/plottool
* https://github.com/Erotemic/vtool
* https://github.com/Erotemic/hesaff
* https://github.com/Erotemic/guitool


bluemellophone's IBEIS modules

* https://github.com/bluemellophone/detecttools
* https://github.com/bluemellophone/pyrf


hjweide's IBEIS modules

* https://github.com/hjweide/pygist


The IBEIS module itself: 

* https://github.com/Erotemic/ibeis

# Environment Setup:

```bash
# The following install script instal ibeis and all dependencies. 
# If it doesnt you can look at the older instructions which follow
# and try to figure it out

# Navigate to your code directory
export CODE_DIR=~/code
mkdir $CODE_DIR
cd $CODE_DIR

# Clone IBEIS
git clone https://github.com/Erotemic/ibeis.git
cd ibeis

# Generate the prereq install script
./_scripts/bootstrap.py

# Run the prereq install script
./_scripts/__install_prereqs__.sh

# Run super_setup to build and install ibeis modules in development mode
# Usually this needs to be run twice. Either way it wont hurt
./super_setup.py --build --develop
./super_setup.py --build --develop
```


###


#### OLD Environment Setup:
```bash
# Navigate to your code directory
export CODE_DIR=~/code
cd $CODE_DIR

# First clone the IBEIS repos
git clone https://github.com/Erotemic/utool.git
git clone https://github.com/Erotemic/vtool.git
git clone https://github.com/Erotemic/plottool.git
git clone https://github.com/Erotemic/guitool.git
git clone https://github.com/Erotemic/hesaff.git
git clone https://github.com/Erotemic/ibeis.git
# Set the previous repos up for development by running
#
# > sudo python setup.py develop
#
# in each directory


# e.g.
sudo python $CODE_DIR/utool/setup.py develop
sudo python $CODE_DIR/vtool/setup.py develop
sudo python $CODE_DIR/hesaff/setup.py develop
sudo python $CODE_DIR/plottool/setup.py develop
sudo python $CODE_DIR/guitool/setup.py develop
sudo python $CODE_DIR/ibeis/setup.py develop


# Then clone these repos (these do not have setup.py files)
git clone https://github.com/bluemellophone/detecttools.git
git clone https://github.com/Erotemic/opencv.git
git clone https://github.com/Erotemic/flann.git
git clone https://github.com/bluemellophone/pyrf.git
# For repos with C++ code use the unix/mingw build script in the repo:
# e.g.
sudo ~/code/opencv/unix_build.sh
sudo ~/code/flann/unix_build.sh
sudo ~/code/pyrf/unix_build.sh

# If you want to train random forests with pyrf clone
# https://github.com/bluemellophone/IBEIS2014.git
# otherwise you dont need this
```


# Example usage

(Note: This list is far from complete)

```bash
#--------------------
# Main Commands
#--------------------
python main.py <optional-arguments> [--help]
python dev.py <optional-arguments> [--help]
# main is the standard entry point to the program
# dev is a more advanced developer entry point

# Useful flags.
# Read code comments in dev.py for more info.
# Careful some commands don't work. Most do.
# --cmd          # shows ipython prompt with useful variables populated
# -w, --wait     # waits (useful for showing plots)
# --gui          # starts the gui as well (dev.py does not show gui by default, main does)
# -t [test]


#--------------------
# PSA: Workdirs:
#--------------------
# IBEIS uses the idea of a work directory for databases.
# Use --set-workdir <path> to set your own, or a gui will popup and ask you about it

# use --db to specify a database in your WorkDir
# --setdb makes that directory your default directory
python dev.py --db <dbname> --setdb

# Or just use the absolute path
python dev.py --dbdir <full-dbpath>


#--------------------
# Examples:
# Here are are some example commands
#--------------------
# Run the queries for each roi with groundtruth in the PZ_Mothers database
# using the best known configuration of parameters
python dev.py --db PZ_Mothers --allgt -t best
python dev.py --db PZ_Mothers --allgt -t score


# View work dir
python dev.py --vwd --prequit

# List known databases
python dev.py -t list_dbs


# Dump/Print contents of params.args as a dict
python dev.py --prequit --dump-argv


#------------------
# Convert a hotspotter database to IBEIS
#------------------
# Set this as your workdir
python dev.py --db PZ_Mothers --setdb
# If its in the same location as a hotspotter db, convert it
python dev.py --convert --force-delete
python dev.py --convert --force-delete --db Database_MasterGrevy_Elleni
# Then interact with your new IBEIS database
python dev.py --cmd --gui 
> rid_list = ibs.get_valid_rids()

# Convinience: Convert ALL hotspotter databases
python dev.py -t convert_hsdbs --force-delete


python dev.py --convert --force-delete --db Frogs
python dev.py --convert --force-delete --db GIR_Tanya
python dev.py --convert --force-delete --db GZ_All
python dev.py --convert --force-delete --db Rhinos_Stewart
python dev.py --convert --force-delete --db WD_Siva
python dev.py --convert --force-delete --db WY_Toads
python dev.py --convert --force-delete --db WS_hard
python dev.py --convert --force-delete --db Wildebeast
python dev.py --convert --force-delete --db PZ_FlankHack
python dev.py --convert --force-delete --db PZ_Mothers


#--------------
# Run Result Inspection
#--------------
python dev.py --convert --force-delete --db Mothers --setdb
python dev.py --db Mothers --setdb
python dev.py --cmd --allgt -t inspect


#---------
# Ingest examples
#---------
# Ingest raw images
python ibeis/ingest/ingest_database.py --db JAG_Kieryn

# Ingest an hsdb
python ibeis/ingest/ingest_hsdb.py --db JAG_Kelly --force-delete

# Merge all jaguar databases into single big database
python main.py --merge-species JAG_


#---------
# Run Tests
#---------
./testsuit/run_tests.sh


#---------------
# Technical Demo
#---------------
python dev.py --db PZ_Mothers --setdb

# See a list of tests
python dev.py -t help

# See a plot of scores
python dev.py --allgt -t scores -w

# Run the best configuration and print out the hard cases
python dev.py --allgt -t best --echo-hardcase

# Look at inspection widget
python dev.py --allgt -t inspect -w


#----------------
# Profiling Code
#----------------

profiler.sh dev.py -t best --db testdb1 --allgt --nocache-query --prof-mod "spatial;linalg;keypoint"
profiler.sh dev.py -t best --db PZ_Mothers --all --nocache-query --prof-mod "spatial;linalg;keypoint"


#----------------
# Test Commands
#----------------
# Set a default DB First
./dev.py --setdb --dbdir /path/to/your/DBDIR
./dev.py --setdb --db YOURDB
./dev.py --setdb --db PZ_Mothers
./dev.py --setdb --db PZ_FlankHack

# List all available tests
./dev.py -t help
# Minimal Database Statistics
./dev.py --allgt -t info
# Richer Database statistics
./dev.py --allgt -t dbinfo
# Print algorithm configurations
./dev.py -t printcfg
# Print database tables
./dev.py -t tables
# Print only the image table
./dev.py -t imgtbl
# View data directory in explorer/finder/nautilus
./dev.py -t vdd


# List all IBEIS databases
./dev.py -t listdbs
# List unconverted hotspotter databases in your workdir
./dev.py -t listhsdbs
# Delete cache
./dev.py -t delete_cache

# Plot of chip-to-chip scores
./dev.py --allgt -t scores -w

# Plot of keypoint-to-keypoint distances
./dev.py --allgt -t dists -w

# See how scores degrade as database size increases
./dev.py --allgt -t upsize -w



# Show Annotation Chips 1, 3, 5, and 11
./dev.py -t show --qaid 1 3 5 11 -w
# Query Annotation Chips 1, 3, 5, and 11
./dev.py -t query --qaid 1 3 5 11 -w
# Inspect spatial verification of annotations 1, 3, 5, and 11
./dev.py -t sver --qaid 1 3 5 11 -w
# Compare matching toggling the gravity vector
./dev.py -t gv --qaid 1 11 -w



# Current Experiments:

./profiler.sh dev.py -t upsize --allgt --quiet --noshow

python dev.py -t upsize --db PZ_Mothers --qaid 1:30:3 -w


dev.py -t upsize --allgt --quiet --noshow
profiler.sh dev.py -t upsize --quiet --db PZ_Mothers --qaid 1:30
python dev.py -t upsize --quiet --db PZ_Mothers --qaid 1:30
python dev.py -t upsize --quiet --db PZ_Mothers --allgt -w

```
