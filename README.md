# extend-dangles - GRASS Addon
Author:    David Pairman <pairmand landcareresearch.co.nz>
  
Published under GNU GPLv3

# Summary
extend-dangles is a Python package to provide a GRASS Addon command `v.extendline`

# Purpose
`v.extendline` is used to extend dangles in a vector map to meet either the another line in the map or another dangle extension, whichever comes first.

Two options control the lenght that the line (dangle) can be extended, being the lesser of:

`maxlen` - Max length im map units that line can be extended (def=200)

`scale` - Maximum length of extension as proportion of original line, disabled if 0 (def=0.5)

`v.extendline --help` provides more information on the command syntax

See also: <em><a href="https://desktop.arcgis.com/en/arcmap/10.3/tools/editing-toolbox/extend-line.htm">ArcMap Extend Line</a></em>

# Reference

This software is used in Manaaki Whenua's paddock boundary segmentation work (Boundary Delineation of Agricultural Fields in Multitemporal Satellite Imagery, https://doi.org/10.1109/JSTARS.2018.2884513.

# License

Copyright:    (C) 2015 by David Pairman, Manaaki Whenua - Landcare Research

This program is free software under the GNU General Public
License (version 3). Read the file COPYING that comes with GRASS
for details.

