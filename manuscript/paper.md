---
title: 'PaddockTS: paddock-level satellite time series analysis of agroecosystem dynamics'
tags:
  - remote sensing
  - Earth observation
  - Sentinel-2
  - satellite time series
  - agricultural field boundaries
  - field-level analysis
  - vegetation phenology
  - agroecosystem
  - agricultural monitoring
authors:
  - name: John T. Burley
    orcid: 0000-0003-4702-5056
    corresponding: true
    affiliation: 1
    email: john.burley3000@gmail.com
  - name: Yasar Adeel Ansari
    affiliation: 1
  - name: Christopher Bradley
    orcid: 0009-0008-2291-8433
    affiliation: 1
  - name: Alex Norton
    orcid: 0000-0001-7708-3914
    affiliation: "1, 2"
  - name: Justin Borevitz
    orcid: 0000-0001-8408-3699
    affiliation: 1
affiliations:
  - index: 1
    name: Research School of Biology, Australian National University, 46 Sullivans Creek Rd, Acton, ACT 2601, Australia
  - index: 2
    name: CSIRO Environment, Aspendale, VIC, Australia
date: 1 September 2026
bibliography: paper.bib
---

# Summary

PaddockTimeSeries (PaddockTS) is an open-source data analysis pipeline that aligns Earth
observation data with agricultural fields, or paddocks—the core land management units where
agricultural decisions are made and outcomes such as yield, phenology, productivity, and soil
condition are recorded. PaddockTS enables scalable agricultural monitoring and research on how
land management and environmental variation shape agroecosystem dynamics. For a user-defined
location and date range in Australia, PaddockTS delineates paddock boundaries from Sentinel-2
time-series imagery using geospatial segmentation or accepts user-provided boundaries,
aggregates Sentinel-2 satellite time series within them, and returns analysis-ready datasets and
graphics describing vegetation dynamics and derived seasonal features. It also retrieves
environmental covariates, including terrain, soil, weather, and water-balance variables. By
summarising vegetation dynamics at the paddock level, PaddockTS makes Earth observation data
easier to integrate with management records, environmental conditions, and agricultural and
ecological outcomes. Its outputs enable comparisons across paddocks, years, and environmental
gradients and provide analysis-ready inputs for agroecosystem modelling and machine-learning
prediction tasks. PaddockTS can be used as a programmable Python workflow for reproducible
research or through a web interface for exploratory analysis without coding.

Software repository: [https://github.com/johnburley3000/paddocktimeseries](https://github.com/johnburley3000/paddocktimeseries)  
Interactive web tool: [https://www.paddocktimeseries.net/](https://www.paddocktimeseries.net/)

# Statement of need

Satellite data are increasingly used to map crops, detect agricultural management and plant
phenology, and estimate field-level productivity and yield [@burke2017; @dandrimont2020;
@vantricht2023; @xie2024]. Their repeated, globally consistent observations create
opportunities to compare how agroecosystems respond to management and environmental
variation across large areas, complementing the scope of purpose-built agronomic experiments
[@cambron2024; @hu2024; @weiss2020]. Such comparisons are important for evaluating how
agricultural management in different contexts affects productivity, resilience to climate
extremes, and carbon stocks [@guan2023; @lobell2025; @nouri2021; @zhou2022].

Realising this potential requires satellite observations to be organised at spatial scales
appropriate to research questions or applications. Remote-sensing analyses commonly operate
at the pixel level or more broadly across land-use categories or administrative regions. However,
practices such as sowing, grazing, fertilisation, irrigation, and harvest—and associated records
of crop development, soil properties, and yield—are often organised by paddock. Paddock-level
summaries therefore provide a complementary scale of analysis that aligns satellite time series
with the spatial units in which management is applied and outcomes are commonly recorded.
Converting dense satellite archives into standardised paddock-level time series also makes
comparisons more tractable at continental or global scales.

PaddockTS addresses this need by providing a reproducible workflow for generating
paddock-level time series and derived features together with relevant environmental covariates.
It is intended for researchers conducting agroecosystem monitoring, comparative analysis,
machine learning, and process-based modelling, as well as practitioners seeking interpretable
summaries of satellite and environmental data that complement local knowledge. The current
implementation focuses on Australia because it builds on Australian Earth observation and
environmental datasets, while its modular architecture supports extension to other regions and
data sources.

# State of the field

PaddockTS builds on several open-access Earth observation datasets and analytical tools. It
retrieves Sentinel-2 NBART surface reflectance through Digital Earth Australia [@dhu2017;
@geoscience2022] and environmental covariates from Copernicus DEM, SILO, SLGA, and
OzWALD [@esa2022; @jeffrey2001; @vandijk2018; @viscarrarossel2015]. It also applies
established spectral indices, an Australian fractional-cover model [@scarth2010; @scarth2022],
and established approaches for estimating phenology metrics [@jonsson2004;
@trotterrobinson2021].

Paddock segmentation presents a distinct challenge within this workflow and is an active area
of research in satellite remote sensing [@corley2026; @muhawenayo2026]. Recent approaches
increasingly use time-series satellite data to exploit differences in vegetation trajectories and
management timing [@watkins2019; @yan2024], although performance remains dependent on
agricultural context, imagery, and model parameterisation [@ferreira2025]. Because paddocks
are transient in time and are not always clearly defined spatial units, particularly in
heterogeneous cropping–pasture landscapes, this motivates flexible workflows that support
different automated segmentation approaches as well as user-supplied polygons to define
paddocks.

PaddockTS’s contribution is to integrate otherwise separate capabilities into a scalable workflow
for time-series analysis of agroecosystem dynamics, with paddocks as the core spatial unit of
analysis. It complements increasingly available field-boundary predictions [e.g.,
@robinson2026] and benchmarking datasets [e.g., @kerner2024]. It differs from platforms that
support data access and custom processing but do not provide this domain-specific workflow
and its standardised outputs by default [@gorelick2017; @haan2023].

# Software design

## Workflow architecture

PaddockTS is organised as a modular workflow that coordinates data acquisition, paddock
delineation, time-series construction, seasonal feature extraction, and visualisation
(\autoref{fig:workflow}). Each analysis is defined by an immutable query object, called `troi`,
specifying the time and region of interest. Maintained in the separate
[`troi`](https://github.com/thestochasticman/troi) package, this object provides a consistent
identity for data retrieval and caching across related geospatial packages.

Workflows begin from either a user-defined region with automated paddock delineation or
user-supplied paddock polygons. Processing steps can be run as a complete pipeline or
independently, with cached intermediate products allowing analyses to resume without
recomputation.

![PaddockTS architecture and typical workflows.\label{fig:workflow}](Figure1_paddockts_workflow_v3.pdf)

## Earth observation and environmental data processing and caching

Sentinel-2 NBART surface-reflectance data are accessed from Digital Earth Australia through the
independently maintained
[`pysentinel2`](https://github.com/thestochasticman/pysentinel2) package. Raw reflectance bands
and Fmask classifications are stored in a sparse, spatially indexed Zarr data cube. For each
request, only missing date/location chunks are downloaded. Overlapping or adjacent queries can
therefore reuse locally available observations. Cloud and shadow masking uses a configurable
procedure within `pysentinel2`, allowing independent testing and development. Cleaned
reflectance data are then used to calculate spectral indices and vegetation fractional cover,
which are also cached for downstream analyses.

Terrain, soil, weather, and water-balance data are retrieved through dedicated packages for
Copernicus DEM, SLGA, SILO, and OzWALD. These packages apply source-appropriate spatial
and temporal caching and return products aligned to the query region and period. Because some
environmental datasets are substantially coarser than Sentinel-2 imagery, they are treated as
contextual or modelling covariates rather than assumed to represent within-paddock variation.

## Paddock segmentation

The default workflow applies a Fourier transform to the normalised difference water index
(NDWI) time series to produce a three-band image summarising temporal variation, which is
supplied to SAMGeo for segmentation [@kirillov2023; @wuosco2023]. As in other time-series-based
approaches, this representation identifies spatial units with relatively consistent temporal
dynamics that differ from their immediate surroundings. Candidate paddock boundaries may
vary with the query date range, reflecting both genuine changes in land management and
uncertainty in the segmentation, including omission and commission errors. PaddockTS
therefore treats automated segmentation as a pragmatic means of approximating field
boundaries at scale rather than as a definitive representation of management units. Predicted
polygons can be filtered geometrically and by vegetation-index trajectories to reduce commission
errors. Applications requiring reliable boundary accuracy should evaluate segmentation results
against appropriate reference data or substitute user-provided boundaries.

## Paddock time series and seasonal features

Paddock polygons are aligned to the Sentinel-2 grid to aggregate median reflectance,
spectral-index, and fractional-cover values by paddock and acquisition date. The resulting series
can be resampled, interpolated, smoothed, and quality checked using configurable settings,
while both observed and processed trajectories are retained. Processed time series are also
divided into paddock-year datasets containing calendar-date and day-of-year coordinates.
Processed NDVI trajectories for each paddock-year are passed to PhenoloPy to estimate the
start, peak, and end of the growing season.

## Data products and visual outputs

PaddockTS preserves outputs from multiple processing stages, including satellite reflectance,
paddock polygons, paddock-by-time and paddock-year datasets, seasonal features, and
environmental covariates. These analysis-ready data products are used by PaddockTS to
generate maps, animations of satellite imagery, annotated paddock calendars, landscape-scale
time-series summaries, environmental diagnostics, and phenology plots. Persistent paddock
identifiers allow time series and derived features to be joined with user-provided attributes and
observations, such as crop type, management activities, yield, or soil measurements.

# Demonstration

The workflow was applied to a mixed cropping–grazing landscape near Milgadara, New South
Wales, Australia, where paddock boundaries and management histories were available.
\autoref{fig:segmentation} compares user-provided paddock boundaries to those detected by
PaddockTS using 2018–2025 Sentinel data. Paddock-level time series of vegetation fractional
cover reveal contrasting trajectories among paddocks and years, which can be viewed alongside
weather and soil-moisture conditions (\autoref{fig:timeseries}). At the individual-paddock scale,
calendar plots arrange satellite observations by week and year, allowing vegetation development
and management transitions to be interpreted alongside user-provided crop labels
(\autoref{fig:calendar}). Paddock-year vegetation-index trajectories can also be converted into
seasonal features, including the estimated start, peak, and end of the growing season
(\autoref{fig:phenology}). Together, these outputs demonstrate how PaddockTS supports
movement between landscape-scale comparison, detailed inspection of individual paddocks,
and analysis-ready seasonal features.

![Paddock boundaries for the PaddockTS demonstration landscape near Milgadara, New
South Wales, Australia. (A) User-provided paddock boundaries overlaid on aerial imagery.
(B) False-colour representation of the Sentinel-2 NDWI time-series Fourier transform
(2018–2025) used for segmentation; (C) resulting candidate paddock boundaries numbered
from largest to smallest.\label{fig:segmentation}](Figure2_Milgadara_segmentation_star.pdf)

![(A) Paddock-level temporal variation in vegetation fractional cover for the 31 largest
paddocks identified in the demonstration run. The colour scale represents the predicted
fractional contributions of bare ground (BG; red), photosynthetic vegetation (PV; green),
and non-photosynthetic vegetation (NPV; blue). Paddock identifiers correspond to
\autoref{fig:segmentation}C. (B–D) Contextual rainfall, soil-moisture and temperature data,
and timing of Sentinel-2 observations.\label{fig:timeseries}](Figure3_paddocktimeseries_and_environmental_JOSS-final.pdf)

![“Calendar view” of an example paddock from the demonstration with recorded crop
rotations, marked by a red star in \autoref{fig:segmentation}A. Sentinel-2 thumbnail images
show RGB derived from the temporally resampled, interpolated, and smoothed series.
Seasonal variation in plant development and senescence is evident, such as canola flowering
visible in 2021 and 2023.\label{fig:calendar}](Figure4_calendarplot_No4.pdf)

![Examples of seasonal features estimated from paddock-level vegetation trajectories.
Panels show processed NDVI time series for selected paddock-years at Milgadara, with start
of season (SoS), peak of season (PoS), and end of season (EoS) indicated.
\label{fig:phenology}](Figure5_phenology_example_v2.pdf)

# Research impact statement

PaddockTS is being used to characterise vegetation dynamics across Australian cropping regions
and investigate how management and environmental variation influence productivity and
resilience to climatic extremes. Its standardised paddock-level time series support comparisons
within and among years across broad bioclimatic gradients, provide imagery and structured
inputs for machine-learning applications, and are being integrated with the DAESim
process-based agroecosystem model [@taghikhah2022]. This integration enables
satellite-observed vegetation trajectories to be compared with modelled dynamics and supports
efforts to distinguish environmental constraints from management-related effects.

At smaller spatial scales, PaddockTS has been applied with Australian land-management
organisations, including the Mulloon Institute and Soils For Life, to examine vegetation
responses where novel management practices and paddock configurations are being trialled to
improve climate resilience. In these applications, user-provided paddock boundaries are used to
compare vegetation dynamics in treatment and reference areas while controlling for
environmental variation. Together, these applications demonstrate the utility of PaddockTS for
large-scale comparative research and for complementing experimental research involving
paddock-level treatments.

# AI usage disclosure

Generative AI tools (ChatGPT, OpenAI; Claude, Anthropic) were used to assist in developing
PaddockTS code and this manuscript. All AI-assisted outputs were critically reviewed, edited,
tested, and validated by the authors. The authors made all scientific, conceptual, and
software-design decisions and take full responsibility for the accuracy and integrity of the
submitted work.

# Acknowledgements

This work was supported by the National Environmental Science Program and computational
resources provided by the National Computational Infrastructure (NCI Australia). We thank
Geoscience Australia, Digital Earth Australia, and the developers of the open-source software
used in this work.

# References
