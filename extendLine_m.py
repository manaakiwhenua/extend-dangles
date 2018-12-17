#!/usr/bin/env python
# -*- coding: utf-8 -*-
############################################################################
#
# MODULE:       extendLine
# AUTHOR(S):    David Pairman
#
# PURPOSE:      Extends vector line dangles (simmilar to Arc function of the same name)
# COPYRIGHT:    (C) 2015 by David Pairman
#
#               This program is free software under the GNU General Public
#               License (version 2). Read the file COPYING that comes with GRASS
#               for details.
# TODO
#    Should cater for boundaries also?
#############################################################################

#%module
#% description: Extends vector line dangles.
#% keyword: vector
#% keyword: dangle
#% keyword: line
#% keyword: geometry
#%end

#%option G_OPT_V_INPUT
#% map=Input map name
#% maxlen=Max length in map units that line can be extended (def=200)
#% scale=Maximum length of extension as proportion of original line, disabled if 0 (def=0.5)
#%end

#%option G_OPT_V_OUTPUT
#%end

#%option
#%end


import math

from grass.script import parser, run_command
from grass.pygrass.vector import VectorTopo
from grass.pygrass.vector import geometry as geo
from grass.pygrass.vector.table import get_path, Table, Columns
import sqlite3
path="$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db"
import gc

def cleanup():
    pass

def extendLine(map, maxlen=200, scale=0.5, debug=False):
#
# map=Input map name
# maxlen=Max length in map units that line can be extended (def=200)
# scale=Maximum length of extension as proportion of original line, disabled if 0 (def=0.5)
# vlen=number of verticies to look back in calculating line end direction (def=1)
# Not sure if it is worth putting this in as parameter.
#

    print("map=",map," maxlen=",maxlen," scale=",scale)
    vlen = 1 # not sure if this is worth putting in as parameter
    cols = [(u'cat',        'INTEGER PRIMARY KEY'),
            (u'parent',     'INTEGER'),
            (u'dend',       'TEXT'),
            (u'orgx',       'DOUBLE PRECISION'),
            (u'orgy',       'DOUBLE PRECISION'),
            (u'search_len', 'DOUBLE PRECISION'),
            (u'search_az',  'DOUBLE PRECISION'),
            (u'best_xid',   'INTEGER'),
            (u'near_x',     'DOUBLE PRECISION'),
            (u'near_y',     'DOUBLE PRECISION'),
            (u'other_cat',  'INTEGER'),
            (u'xtype',      'TEXT'),
            (u'x_len',      'DOUBLE PRECISION')]
    extend=VectorTopo('extend')
    if extend.exist():
        extend.remove()
    extend.open('w', tab_name = 'extend', tab_cols = cols)
#
# Go through input map, looking at each line and it's two nodes to find nodes
# with only a single line starting/ending there - i.e. a dangle.
# For each found, generate an extension line in the new map "extend"
#
    inMap = VectorTopo(map)
    inMap.open('r')
    dangleCnt=0
    tickTrig=len(inMap)
    print("Searching {} features for dangles".format(tickTrig))
    tickTrig=round(tickTrig/20)
    progress=0
    ticker=0
    for ln in inMap:
        ticker = (ticker + 1) % tickTrig
        if ticker == 0:
          progress = progress+5
          print("Progress={}%".format(progress))
        if ln.gtype==2: # Only process lines
            for nd in ln.nodes():
                if nd.nlines == 1:   # We have a dangle
                    dangleCnt=dangleCnt+1
                    vtx=min(len(ln)-1,vlen)
                    if len([1 for _ in nd.lines(only_out=True)])==1: # Dangle starting at node
                        dend = "head"
                        sx = ln[0].x
                        sy = ln[0].y
                        dx = sx - ln[vtx].x
                        dy = sy - ln[vtx].y
                    else:                                            # Dangle ending at node
                        dend = "tail"
                        sx = ln[-1].x
                        sy = ln[-1].y
                        dx = sx - ln[-(vtx+1)].x
                        dy = sy - ln[-(vtx+1)].y
                    endaz = math.atan2(dy,dx)
                    if scale>0:
                        extLen = min(ln.length() * scale, maxlen)
                    else:
                        extLen = maxlen
                    ex = extLen*math.cos(endaz)+sx
                    ey = extLen*math.sin(endaz)+sy
                    extLine = geo.Line([(sx,sy),(ex,ey)])
                    quiet=extend.write(extLine, (ln.cat,dend,sx,sy,extLen,endaz,0,0,0,0,'null',extLen))
    print("{} dangle nodes found, committing table extend".format(dangleCnt))  
    extend.table.conn.commit()
    extend.close(build=True, release=True)
    inMap.close()

#
# Create two tables where extensions intersect;
# 1. intersect with original lines
# 2. intersect with self - to extract intersects between extensions 
#
# First the intersects with original lines
    print("Searching for intersects between potential extensions and original lines") 
    table_isectIn = Table('isectIn',
                connection=sqlite3.connect(get_path(path)))
    if table_isectIn.exist():
        table_isectIn.drop(force=True)
    run_command("v.distance",
                flags = 'a',
                overwrite = True,
                quiet = True,
                from_ = "extend",
                from_type = "line",
                to = map, 
                to_type = "line",
                dmax = "0",
                upload = "cat,dist,to_x,to_y",
                column = "near_cat,dist,nx,ny",
                table = "isectIn")
# Will have touched the dangle it comes from, so remove those touches
    run_command("db.execute",
                sql = "DELETE FROM isectIn WHERE rowid IN (SELECT isectIn.rowid FROM isectIn INNER JOIN extend ON from_cat=cat WHERE near_cat=parent)",
                driver = "sqlite",
                database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    run_command("db.execute",
                sql = "ALTER TABLE isectIn ADD ntype VARCHAR",
                driver = "sqlite",
                database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    run_command("db.execute",
                sql = "UPDATE isectIn SET ntype = 'orig' ",
                driver = "sqlite",
                database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
#
# Now second self intersect table
#
    print("Searching for intersects of potential extensions") 
    table_isectX = Table('isectX',
                connection=sqlite3.connect(get_path(path)))
    if table_isectX.exist():
        table_isectX.drop(force=True)
    run_command("v.distance",
                flags = 'a',
                overwrite = True,
                quiet = True,
                from_ = "extend",
                from_type = "line",
                to = "extend", 
                to_type = "line",
                dmax = "0",
                upload = "cat,dist,to_x,to_y",
                column = "near_cat,dist,nx,ny",
                table = "isectX")
# Obviously all extensions will intersect with themself, so remove those "intersects"
    run_command("db.execute",
                sql = "DELETE FROM isectX WHERE from_cat = near_cat",
                driver = "sqlite",
                database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    run_command("db.execute",
                sql = "ALTER TABLE isectX ADD ntype VARCHAR",
                driver = "sqlite",
                database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    run_command("db.execute",
                sql = "UPDATE isectX SET ntype = 'ext' ",
                driver = "sqlite",
                database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
#
# Combine the two tables and add a few more attributes
#				
    run_command("db.execute",
                sql = "INSERT INTO isectIn SELECT * FROM isectX",
                driver = "sqlite",
                database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    cols_isectIn = Columns('isectIn',
                connection=sqlite3.connect(get_path(path)))
    cols_isectIn.add(['from_x'], ['DOUBLE PRECISION'])
    cols_isectIn.add(['from_y'], ['DOUBLE PRECISION'])
    cols_isectIn.add(['ext_len'], ['DOUBLE PRECISION'])
# Get starting coordinate at the end of the dangle
    run_command("db.execute",
                sql = "UPDATE isectIn SET from_x = (SELECT extend.orgx FROM extend WHERE from_cat=extend.cat)",
                driver = "sqlite",
                database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    run_command("db.execute",
                sql = "UPDATE isectIn SET from_y = (SELECT extend.orgy FROM extend WHERE from_cat=extend.cat)",
                driver = "sqlite",
                database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    table_isectIn.conn.commit()
# For each intersect point, calculate the distance along extension line from end of dangle
# Would be nicer to do this in the database but SQLite dosen't support sqrt or exponents
    print("Calculating distances of intersects along potential extensions")
    cur=table_isectIn.execute(sql_code="SELECT rowid, from_x, from_y, nx, ny FROM isectIn")
    for row in cur.fetchall():
        rowid,fx,fy,nx,ny = row
        x_len=math.sqrt((fx-nx)**2+(fy-ny)**2)
        sqlStr="UPDATE isectIn SET ext_len={:.8f} WHERE rowid={:d}".format(x_len,rowid)
        table_isectIn.execute(sql_code=sqlStr)
    print("Ready to commit isectIn changes")
    table_isectIn.conn.commit()
# Remove any zero distance from end of their dangle.
# This happens when another extension intersects exactly at that point
    run_command("db.execute",
                sql = "DELETE FROM isectIn WHERE ext_len = 0.0",
                driver = "sqlite",
                database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    table_isectIn.conn.commit()

# Go through the extensions and find the intersect closest to each origin.
    print("Searching for closest intersect for each potential extension") 

# db.execute sql="ALTER TABLE extend_t1 ADD COLUMN bst INTEGER"
# db.execute sql="ALTER TABLE extend_t1 ADD COLUMN nrx DOUBLE PRECISION"
# db.execute sql="ALTER TABLE extend_t1 ADD COLUMN nry DOUBLE PRECISION"
# db.execute sql="ALTER TABLE extend_t1 ADD COLUMN ocat TEXT"
#    run_command("db.execute", 
#                sql = "INSERT OR REPLACE INTO extend_t1 (bst, nrx, nry, ocat) VALUES ((SELECT isectIn.rowid, ext_len, nx, ny, near_cat, ntype FROM isectIn WHERE from_cat=extend_t1.cat ORDER BY ext_len ASC LIMIT 1))",
#               driver = "sqlite",
#               database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")

    print("CREATE index")
    run_command("db.execute",
                sql = "CREATE INDEX idx_from_cat ON isectIn (from_cat)",
                driver = "sqlite", database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    print("UPDATE best_xid")
    run_command("db.execute",
                sql = "UPDATE extend SET best_xid = (SELECT isectIn.rowid FROM isectIn WHERE from_cat=extend.cat ORDER BY ext_len ASC LIMIT 1)",
                driver = "sqlite", database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    print("UPDATE x_len")
    run_command("db.execute",
                sql = "UPDATE extend SET x_len = (SELECT ext_len FROM isectIn WHERE from_cat=extend.cat ORDER BY ext_len ASC LIMIT 1)",
                driver = "sqlite", database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    print("UPDATE near_x")
    run_command("db.execute",
                sql = "UPDATE extend SET near_x = (SELECT nx FROM isectIn WHERE from_cat=extend.cat ORDER BY ext_len ASC LIMIT 1)",
                driver = "sqlite", database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    print("UPDATE near_y")
    run_command("db.execute",
                sql = "UPDATE extend SET near_y = (SELECT ny FROM isectIn WHERE from_cat=extend.cat ORDER BY ext_len ASC LIMIT 1)",
                driver = "sqlite", database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    print("UPDATE other_cat")
    run_command("db.execute",
                sql = "UPDATE extend SET other_cat = (SELECT near_cat FROM isectIn WHERE from_cat=extend.cat ORDER BY ext_len ASC LIMIT 1)",
                driver = "sqlite", database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    print("UPDATE xtype")
    run_command("db.execute",
                sql = "UPDATE extend SET xtype = (SELECT ntype FROM isectIn WHERE from_cat=extend.cat ORDER BY ext_len ASC LIMIT 1)",
                driver = "sqlite", database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    print("DROP index")
    run_command("db.execute", sql = "DROP INDEX idx_from_cat",
                driver = "sqlite", database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    print("CREATE index on near_cat")
    run_command("db.execute",
                sql = "CREATE INDEX idx_near_cat ON isectIn (near_cat)",
                driver = "sqlite", database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")


    quiet=table_isectIn.filters.select('rowid','ext_len','nx','ny','near_cat','ntype')
#    quiet=table_isectIn.filters.order_by(['ext_len ASC'])
    quiet=table_isectIn.filters.order_by('ext_len ASC')
    quiet=table_isectIn.filters.limit(1)
    table_extend = Table('extend',
                connection=sqlite3.connect(get_path(path)))

# Code below was relplaced by commands above untill memory problem can be sorted
#    table_extend.filters.select('cat')
#    cur=table_extend.execute()
#    updateCnt = 0
#    for row in cur.fetchall():
#        cat, = row
#        quiet=table_isectIn.filters.where('from_cat={:d}'.format(cat))

##SELECT rowid, ext_len, nx, ny, near_cat, ntype FROM isectIn WHERE from_cat=32734 ORDER BY ext_len ASC LIMIT 1

#        x_sect=table_isectIn.execute().fetchone()
#        if x_sect is not None:
#            x_rowid, ext_len, nx, ny, other_cat, ntype = x_sect
#            sqlStr="UPDATE extend SET best_xid={:d}, x_len={:.8f}, near_x={:.8f}, near_y={:.8f}, other_cat={:d}, xtype='{}' WHERE cat={:d}".format(x_rowid, ext_len, nx, ny, other_cat, ntype, cat) 
#            table_extend.execute(sql_code=sqlStr)
## Try periodic commit to avoide crash! 
#            updateCnt = (updateCnt + 1) % 10000
#            if updateCnt == 0:
#              table_extend.conn.commit()
    print("Ready to commit extend changes")
    table_extend.conn.commit()
#
# There may be extensions that crossed, and that intersection chosen by one but 
# not "recripricated" by the other.
# Need to remove those possibilities and allow the jilted extension to re-search.
#
    print("Deleting intersects already resolved")
    run_command("db.execute",
                sql = "DELETE FROM isectIn WHERE rowid IN (SELECT isectIn.rowid FROM isectIn JOIN extend ON near_cat=cat WHERE ntype='ext' AND xtype!='null')",  #"AND from_cat!=other_cat" no second chance!
                driver = "sqlite",
                database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db")
    table_isectIn.conn.commit()
    print("Deleting complete")

# To find the jilted - need a copy of extensions that have found an 
# intersection (won't overwrite so drop first)
    print("Re-searching for mis-matched intersects between potential extensions") 
    table_imatch = Table('imatch',
                connection=sqlite3.connect(get_path(path)))
    if table_imatch.exist():
        table_imatch.drop(force=True)
    wvar="xtype!='null'"
#    print(wvar)
    run_command("db.copy",
	        overwrite = True,
                quiet = True,
                from_driver = "sqlite",
                from_database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db",
                from_table = "extend",
                to_driver = "sqlite",
                to_database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db",
                to_table = "imatch",
                where = wvar)
# Memory problems?
    if gc.isenabled():
      print("Garbage collection enabled - forcing gc cycle")
      gc.collect()
    else:
      print("Garbage collection not enabled")
# Ensure tables are commited
    table_extend.conn.commit()
    table_imatch.conn.commit()
    table_isectIn.conn.commit()
# Identify the jilted
    sqlStr = "SELECT extend.cat FROM extend JOIN imatch ON extend.other_cat=imatch.cat WHERE extend.xtype='ext' and extend.cat!=imatch.other_cat"
    cur=table_extend.execute(sql_code=sqlStr)
    updateCnt = 0
    for row in cur.fetchall():
        cat, = row
        print("Reworking extend.cat={}".format(cat))
        quiet=table_isectIn.filters.where('from_cat={:d}'.format(cat))
        #print("SQL: {}".format(table_isectIn.filters.get_sql()))
        x_sect=table_isectIn.execute().fetchone()  ## Problem here under modules
        if x_sect is None:
            sqlStr="UPDATE extend SET best_xid=0, x_len=search_len, near_x=0, near_y=0, other_cat=0, xtype='null' WHERE cat={:d}".format(cat)
        else:
            x_rowid, ext_len, nx, ny, other_cat, ntype = x_sect
            sqlStr="UPDATE extend SET best_xid={:d}, x_len={:.8f}, near_x={:.8f}, near_y={:.8f}, other_cat={:d}, xtype='{}' WHERE cat={:d}".format(x_rowid, ext_len, nx, ny, other_cat, ntype, cat) 
        table_extend.execute(sql_code=sqlStr)
## Try periodic commit to avoide crash! 
        updateCnt = (updateCnt + 1) % 1000
        if (updateCnt == 0) or (cat == 750483):
            print("XXXXXXXXXXX Committing table_extend XXXXXXXXXXXXXXXXXXXXXX")
            table_extend.conn.commit()

    print("Committing adjustments to table extend")
    table_extend.conn.commit()
#
# For debugging, create a map with the chosen intersect points
#
    if debug:
        wvar="xtype!='null' AND x_len!=0"
#        print(wvar)
        run_command("v.in.db",
                overwrite = True,
                quiet = True,
                table = "extend",
                driver = "sqlite",
                database = "$GISDBASE/$LOCATION_NAME/$MAPSET/sqlite/sqlite.db",
                x = "near_x",
                y = "near_y",
                key = "cat",
                where = wvar,
                output = "chosen")
#
# Finally adjust the dangle lines in input map - use a copy till it's all debugged!
#
    run_command("g.copy",
                overwrite = True,
                quiet = True,
                vector = map+","+map+"_extend")
# Get info for lines that need extending
    table_extend.filters.select('parent, dend, near_x, near_y, search_az, xtype')
    table_extend.filters.where("xtype!='null'")
    extLines = table_extend.execute().fetchall()
    cat_mods=[ext[0] for ext in extLines]
    tickTrig=len(cat_mods)
    print("Extending {} dangles".format(tickTrig))
    tickTrig=round(tickTrig/20)
    progress=0
    ticker=0

# Open up the original (copy) and work through looking for lines that need modifying
    inMap=VectorTopo(map+"_extend")
    inMap.open('rw', tab_name = map+"_extend")

    for ln_idx in range(len(inMap)):
        ln = inMap.read(ln_idx+1)
        if ln.gtype==2: # Only process lines
            while ln.cat in cat_mods:      # Note: could be 'head' and 'tail'
                ticker = (ticker + 1) % tickTrig
                if ticker == 0:
                  progress = progress+5
                  print("Progress={}%".format(progress))
                cat_idx=cat_mods.index(ln.cat)
                cat, dend, nx, ny, endaz, xtype  = extLines.pop(cat_idx)
                dump = cat_mods.pop(cat_idx)
                if xtype == 'orig':  # Overshoot by 0.1 as break lines is unreliable
                  nx = nx + 0.1*math.cos(endaz)
                  ny = ny + 0.1*math.sin(endaz)
                newEnd=geo.Point(x=nx, y=ny, z=None)
                if dend == 'head':
                    ln.insert(0,newEnd)
                else:      # 'tail'
                    ln.append(newEnd)
                quiet=inMap.rewrite(ln_idx+1,ln)
        else:
            quite=inMap.delete(ln_idx+1)
## Try periodic commit and garbage collection to avoide crash! 
        if (ln_idx % 1000) == 0:
#           inMap.table.conn.commit()  - no such thing - Why??
            if gc.isenabled():
              quiet = gc.collect()

    inMap.close(build=True, release=True)
    print("extendLines completing")
#
# Clean up temporary tables and maps                    
#
    if not debug:
        table_isectIn.drop(force=True)
        table_isectX.drop(force=True)
        table_imatch.drop(force=True)
        extend.remove()
        chosen=VectorTopo('chosen')
        if chosen.exist():
            chosen.remove()
    return 0

if __name__ == "__main__":
    options, flags = parser()
    atexit.register(cleanup)
    sys.exit(main())
