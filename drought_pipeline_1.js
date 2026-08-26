// TUNISIA DROUGHT EARLY WARNING SYSTEM
// EXTRACTING ENVIRONMENTAL DATA  with Google Earth Engine (https://code.earthengine.google.com/)


// INPUT: Tunisia_gov shapefiles

// OUTPUT:
//   GEE-output/tunisia_drought_monthly.csv
//   GEE-output/tunisia_drought_latest.csv
//   GEE-output/governorates_latest.geojson



// 1. CONFIGURATION

var governorates = ee.FeatureCollection(
  "projects/drought-system/assets/Tunisia_gov"
);

// GOVERNORATE ATTRIBUTE FIELDS

var GOV_ID_FIELD = 'gid';

var GOV_NAME_FIELD = 'shape1';



var START_DATE = '2001-01-01';

var END_DATE = '2026-08-01';


// EXPORT CONFIGURATION

var EXPORT_FOLDER =
    'Tunisia_Drought';


// 2. DATASETS

// CHIRPS DAILY PRECIPITATION

var CHIRPS =
    ee.ImageCollection(
        'UCSB-CHG/CHIRPS/DAILY'
    );


// ERA5-LAND MONTHLY

var ERA5 =
    ee.ImageCollection(
        'ECMWF/ERA5_LAND/MONTHLY_AGGR'
    );


// MODIS NDVI

var MODIS_NDVI =
    ee.ImageCollection(
        'MODIS/061/MOD13Q1'
    );


// MODIS LST

var MODIS_LST =
    ee.ImageCollection(
        'MODIS/061/MOD11A2'
    );


// 3. CHECK GOVERNORATE INPUT

print(
    'Governorate layer:',
    governorates
);

print(
    'Number of governorates:',
    governorates.size()
);

print(
    'First governorate:',
    governorates.first()
);

print(
    'Governorate fields:',
    governorates
        .first()
        .propertyNames()
);


// 4. STANDARDIZE GOVERNORATE ATTRIBUTES


var governorates_standardized =
    governorates.map(
        function(feature) {

            return feature.set({

                governorate_id:
                    ee.String(
                        feature.get(
                            GOV_ID_FIELD
                        )
                    ),

                governorate_name:
                    ee.String(
                        feature.get(
                            GOV_NAME_FIELD
                        )
                    )

            });

        }
    );


print(
    'Standardized governorate:',
    governorates_standardized.first()
);


// 5. VERIFY EXACTLY 24 GOVERNORATES

print(
    'Governorate count:',
    governorates_standardized.size()
);


// 6. CREATE MONTH LIST

var start =
    ee.Date(
        START_DATE
    );

var end =
    ee.Date(
        END_DATE
    );

var numberOfMonths =
    end.difference(
        start,
        'month'
    );

var monthOffsets =
    ee.List.sequence(
        0,
        numberOfMonths.subtract(1)
    );


// 7. PREPARE MODIS NDVI
//
// MOD13Q1 NDVI scale factor:
//
// 0.0001
//
// DetailedQA bits 0-1:
//
// 0 = good quality
//

function prepareNDVI(image) {

    var qa =
        image.select(
            'DetailedQA'
        );

    var good =
        qa
            .bitwiseAnd(3)
            .eq(0);

    return image
        .updateMask(good)
        .select('NDVI')
        .multiply(0.0001)
        .rename('ndvi')
        .copyProperties(
            image,
            [
                'system:time_start'
            ]
        );

}


var NDVI_COLLECTION =
    MODIS_NDVI
        .filterDate(
            START_DATE,
            END_DATE
        )
        .map(
            prepareNDVI
        );


// 8. PREPARE MODIS LST


function prepareLST(image) {

    var qa =
        image.select(
            'QC_Day'
        );

    var good =
        qa
            .bitwiseAnd(3)
            .eq(0);

    return image
        .updateMask(good)
        .select(
            'LST_Day_1km'
        )
        .multiply(0.02)
        .subtract(273.15)
        .rename('lst_c')
        .copyProperties(
            image,
            [
                'system:time_start'
            ]
        );

}


var LST_COLLECTION =
    MODIS_LST
        .filterDate(
            START_DATE,
            END_DATE
        )
        .map(
            prepareLST
        );


// 9. PREPARE ERA5-LAND TEMPERATURE

var ERA5_TEMPERATURE =
    ERA5
        .filterDate(
            START_DATE,
            END_DATE
        )
        .select(
            'temperature_2m'
        )
        .map(
            function(image) {

                return image
                    .subtract(273.15)
                    .rename(
                        'temperature_c'
                    )
                    .copyProperties(
                        image,
                        [
                            'system:time_start'
                        ]
                    );

            }
        );


// 10. PREPARE ERA5-LAND PET


var ERA5_PET =
    ERA5
        .filterDate(
            START_DATE,
            END_DATE
        )
        .select(
            'potential_evaporation_sum'
        )
        .map(
            function(image) {

                return image
                    .multiply(1000)
                    .rename(
                        'pet_mm'
                    )
                    .copyProperties(
                        image,
                        [
                            'system:time_start'
                        ]
                    );

            }
        );


// 11. PREPARE ERA5-LAND SOIL MOISTURE


var ERA5_SOIL =
    ERA5
        .filterDate(
            START_DATE,
            END_DATE
        )
        .select(
            'volumetric_soil_water_layer_1'
        )
        .map(
            function(image) {

                return image
                    .rename(
                        'soil_moisture'
                    )
                    .copyProperties(
                        image,
                        [
                            'system:time_start'
                        ]
                    );

            }
        );


// 12. EMPTY IMAGE HELPER

function emptyImage(
    bandName
) {

    return ee.Image(0)
        .rename(
            bandName
        )
        .updateMask(
            ee.Image(0)
        );

}


// 13. CREATE MONTHLY ENVIRONMENTAL IMAGE

function createMonthlyImage(
    monthOffset
) {

    var monthStart =
        start.advance(
            monthOffset,
            'month'
        );

    var monthEnd =
        monthStart.advance(
            1,
            'month'
        );


    var year =
        monthStart.get(
            'year'
        );

    var month =
        monthStart.get(
            'month'
        );


    // RAINFALL

    var rainfallCollection =
        CHIRPS
            .filterDate(
                monthStart,
                monthEnd
            )
            .select(
                'precipitation'
            );


    var rainfall =
        ee.Image(
            ee.Algorithms.If(

                rainfallCollection
                    .size()
                    .gt(0),

                rainfallCollection.sum(),

                emptyImage(
                    'rainfall_mm'
                )

            )
        )
        .rename(
            'rainfall_mm'
        );


    // TEMPERATURE

    var temperatureCollection =
        ERA5_TEMPERATURE
            .filterDate(
                monthStart,
                monthEnd
            );


    var temperature =
        ee.Image(
            ee.Algorithms.If(

                temperatureCollection
                    .size()
                    .gt(0),

                temperatureCollection.first(),

                emptyImage(
                    'temperature_c'
                )

            )
        )
        .rename(
            'temperature_c'
        );


    // PET

    var petCollection =
        ERA5_PET
            .filterDate(
                monthStart,
                monthEnd
            );


    var pet =
        ee.Image(
            ee.Algorithms.If(

                petCollection
                    .size()
                    .gt(0),

                petCollection.first(),

                emptyImage(
                    'pet_mm'
                )

            )
        )
        .rename(
            'pet_mm'
        );


    // SOIL MOISTURE

    var soilCollection =
        ERA5_SOIL
            .filterDate(
                monthStart,
                monthEnd
            );


    var soil =
        ee.Image(
            ee.Algorithms.If(

                soilCollection
                    .size()
                    .gt(0),

                soilCollection.first(),

                emptyImage(
                    'soil_moisture'
                )

            )
        )
        .rename(
            'soil_moisture'
        );


    // NDVI

    var ndviCollection =
        NDVI_COLLECTION
            .filterDate(
                monthStart,
                monthEnd
            );


    var ndvi =
        ee.Image(
            ee.Algorithms.If(

                ndviCollection
                    .size()
                    .gt(0),

                ndviCollection.mean(),

                emptyImage(
                    'ndvi'
                )

            )
        )
        .rename(
            'ndvi'
        );


    // LST

    var lstCollection =
        LST_COLLECTION
            .filterDate(
                monthStart,
                monthEnd
            );


    var lst =
        ee.Image(
            ee.Algorithms.If(

                lstCollection
                    .size()
                    .gt(0),

                lstCollection.mean(),

                emptyImage(
                    'lst_c'
                )

            )
        )
        .rename(
            'lst_c'
        );


    // COMBINE

    var monthly =
        ee.Image.cat([

            rainfall,

            temperature,

            pet,

            ndvi,

            lst,

            soil

        ]);


    // METADATA

    return monthly.set({

        'system:time_start':
            monthStart.millis(),

        'date':
            monthStart.format(
                'YYYY-MM-dd'
            ),

        'year':
            year,

        'month':
            month

    });

}


// 14. BUILD MONTHLY COLLECTION

var monthlyCollection =
    ee.ImageCollection.fromImages(
        monthOffsets.map(
            createMonthlyImage
        )
    );


print(
    'Monthly collection:',
    monthlyCollection
);

print(
    'Monthly image count:',
    monthlyCollection.size()
);


// 15. CRITICAL BAND CHECK

print(
    'First monthly image bands:',
    monthlyCollection
        .first()
        .bandNames()
);


// 16. NDVI CLIMATOLOGY

var ndviMinByMonth =
    ee.ImageCollection.fromImages(

        ee.List.sequence(
            1,
            12
        ).map(
            function(month) {

                return monthlyCollection
                    .filter(
                        ee.Filter.calendarRange(
                            month,
                            month,
                            'month'
                        )
                    )
                    .select(
                        'ndvi'
                    )
                    .min()
                    .rename(
                        'ndvi_min'
                    )
                    .set(
                        'month',
                        month
                    );

            }
        )

    );


var ndviMaxByMonth =
    ee.ImageCollection.fromImages(

        ee.List.sequence(
            1,
            12
        ).map(
            function(month) {

                return monthlyCollection
                    .filter(
                        ee.Filter.calendarRange(
                            month,
                            month,
                            'month'
                        )
                    )
                    .select(
                        'ndvi'
                    )
                    .max()
                    .rename(
                        'ndvi_max'
                    )
                    .set(
                        'month',
                        month
                    );

            }
        )

    );


// 17. LST CLIMATOLOGY

var lstMinByMonth =
    ee.ImageCollection.fromImages(

        ee.List.sequence(
            1,
            12
        ).map(
            function(month) {

                return monthlyCollection
                    .filter(
                        ee.Filter.calendarRange(
                            month,
                            month,
                            'month'
                        )
                    )
                    .select(
                        'lst_c'
                    )
                    .min()
                    .rename(
                        'lst_min'
                    )
                    .set(
                        'month',
                        month
                    );

            }
        )

    );


var lstMaxByMonth =
    ee.ImageCollection.fromImages(

        ee.List.sequence(
            1,
            12
        ).map(
            function(month) {

                return monthlyCollection
                    .filter(
                        ee.Filter.calendarRange(
                            month,
                            month,
                            'month'
                        )
                    )
                    .select(
                        'lst_c'
                    )
                    .max()
                    .rename(
                        'lst_max'
                    )
                    .set(
                        'month',
                        month
                    );

            }
        )

    );


// 18. ADD VCI / TCI / VHI

function addVegetationIndicators(
    image
) {

    var month =
        ee.Number(
            image.get(
                'month'
            )
        );


    // NDVI MIN

    var ndviMin =
        ee.Image(
            ndviMinByMonth
                .filter(
                    ee.Filter.eq(
                        'month',
                        month
                    )
                )
                .first()
        );


    // NDVI MAX

    var ndviMax =
        ee.Image(
            ndviMaxByMonth
                .filter(
                    ee.Filter.eq(
                        'month',
                        month
                    )
                )
                .first()
        );


    // LST MIN

    var lstMin =
        ee.Image(
            lstMinByMonth
                .filter(
                    ee.Filter.eq(
                        'month',
                        month
                    )
                )
                .first()
        );


    // LST MAX

    var lstMax =
        ee.Image(
            lstMaxByMonth
                .filter(
                    ee.Filter.eq(
                        'month',
                        month
                    )
                )
                .first()
        );


    // NDVI MONTHLY MEAN

    var ndviMean =
        monthlyCollection
            .filter(
                ee.Filter.calendarRange(
                    month,
                    month,
                    'month'
                )
            )
            .select(
                'ndvi'
            )
            .mean();


    // NDVI ANOMALY

    var ndviAnomaly =
        image
            .select(
                'ndvi'
            )
            .subtract(
                ndviMean
            )
            .rename(
                'ndvi_anomaly'
            );


    // VCI

    var ndviRange =
        ndviMax
            .subtract(
                ndviMin
            );


    var vci =
        image
            .select(
                'ndvi'
            )
            .subtract(
                ndviMin
            )
            .divide(
                ndviRange
            )
            .multiply(100)
            .clamp(
                0,
                100
            )
            .rename(
                'vci'
            );


    // LST MONTHLY MEAN

    var lstMean =
        monthlyCollection
            .filter(
                ee.Filter.calendarRange(
                    month,
                    month,
                    'month'
                )
            )
            .select(
                'lst_c'
            )
            .mean();


    // LST ANOMALY

    var lstAnomaly =
        image
            .select(
                'lst_c'
            )
            .subtract(
                lstMean
            )
            .rename(
                'lst_anomaly'
            );


    // TCI

    var lstRange =
        lstMax
            .subtract(
                lstMin
            );


    var tci =
        lstMax
            .subtract(
                image.select(
                    'lst_c'
                )
            )
            .divide(
                lstRange
            )
            .multiply(100)
            .clamp(
                0,
                100
            )
            .rename(
                'tci'
            );


    // VHI

    var vhi =
        vci
            .multiply(0.5)
            .add(
                tci.multiply(0.5)
            )
            .rename(
                'vhi'
            );


    // ADD INDICATORS

    return image
        .addBands(
            ndviAnomaly
        )
        .addBands(
            vci
        )
        .addBands(
            lstAnomaly
        )
        .addBands(
            tci
        )
        .addBands(
            vhi
        );

}


// 19. APPLY VEGETATION INDICATORS

var vegetationCollection =
    monthlyCollection.map(
        addVegetationIndicators
    );


// 20. SOIL MOISTURE ANOMALY

function addSoilMoistureIndicators(
    image
) {

    var month =
        ee.Number(
            image.get(
                'month'
            )
        );


    var soilClimatology =
        vegetationCollection
            .filter(
                ee.Filter.calendarRange(
                    month,
                    month,
                    'month'
                )
            )
            .select(
                'soil_moisture'
            )
            .mean();


    var soilAnomaly =
        image
            .select(
                'soil_moisture'
            )
            .subtract(
                soilClimatology
            )
            .rename(
                'soil_moisture_anomaly'
            );


    var soilAnomalyPct =
        soilAnomaly
            .divide(
                soilClimatology
            )
            .multiply(100)
            .rename(
                'soil_moisture_anomaly_pct'
            );


    return image
        .addBands(
            soilAnomaly
        )
        .addBands(
            soilAnomalyPct
        );

}


var finalCollection =
    vegetationCollection.map(
        addSoilMoistureIndicators
    );


// 21. FINAL BAND VERIFICATION

print(
    'FINAL BANDS:',
    finalCollection
        .first()
        .bandNames()
);




// 22. REDUCE TO GOVERNORATES


function reduceMonthlyImage(
    image
) {

    var date =
        ee.Date(
            image.get(
                'system:time_start'
            )
        );


    var dateString =
        date.format(
            'YYYY-MM-dd'
        );


    var year =
        date.get(
            'year'
        );


    var month =
        date.get(
            'month'
        );


    var reduced =
        image.reduceRegions({

            collection:
                governorates_standardized,

            reducer:
                ee.Reducer.mean(),

            scale:
                11132,

            tileScale:
                4

        });


    return reduced.map(
        function(feature) {

            return feature.set({

                date:
                    dateString,

                year:
                    year,

                month:
                    month

            });

        }
    );

}


// 23. CREATE GOVERNORATE × MONTH DATASET

var monthlyGovernorates =
    finalCollection
        .map(
            reduceMonthlyImage
        )
        .flatten();


print(
    'Governorate-month dataset:',
    monthlyGovernorates
);

print(
    'First governorate-month row:',
    monthlyGovernorates.first()
);


// 24. EXPORT COLUMNS

var exportFields = [

    'governorate_id',

    'governorate_name',

    'date',

    'year',

    'month',

    'rainfall_mm',

    'temperature_c',

    'pet_mm',

    'ndvi',

    'ndvi_anomaly',

    'vci',

    'lst_c',

    'lst_anomaly',

    'tci',

    'soil_moisture',

    'soil_moisture_anomaly',

    'soil_moisture_anomaly_pct',

    'vhi'

];


// 25. EXPORT MONTHLY CSV

Export.table.toDrive({

    collection:
        monthlyGovernorates.select(
            exportFields
        ),

    description:
        'tunisia_drought_monthly',

    folder:
        EXPORT_FOLDER,

    fileNamePrefix:
        'tunisia_drought_monthly',

    fileFormat:
        'CSV'

});


// 26. GET LATEST COMPLETE MONTH

var latestImage =
    ee.Image(
        finalCollection
            .sort(
                'system:time_start',
                false
            )
            .first()
    );


var latestDate =
    ee.Date(
        latestImage.get(
            'system:time_start'
        )
    );


print(
    'Latest complete month:',
    latestDate.format(
        'YYYY-MM-dd'
    )
);


// 27. REDUCE LATEST IMAGE

var latestGovernorates =
    latestImage
        .reduceRegions({

            collection:
                governorates_standardized,

            reducer:
                ee.Reducer.mean(),

            scale:
                11132,

            tileScale:
                4

        })
        .map(
            function(feature) {

                return feature.set({

                    date:
                        latestDate.format(
                            'YYYY-MM-dd'
                        ),

                    year:
                        latestDate.get(
                            'year'
                        ),

                    month:
                        latestDate.get(
                            'month'
                        )

                });

            }
        );


// 28. EXPORT LATEST CSV

Export.table.toDrive({

    collection:
        latestGovernorates.select(
            exportFields
        ),

    description:
        'tunisia_drought_latest',

    folder:
        EXPORT_FOLDER,

    fileNamePrefix:
        'tunisia_drought_latest',

    fileFormat:
        'CSV'

});


// 29. CREATE MAP-READY GOVERNORATE GEOJSON


var latestMap =
    governorates_standardized.map(
        function(governorate) {

            var govId =
                governorate.get(
                    'governorate_id'
                );


            var current =
                latestGovernorates
                    .filter(
                        ee.Filter.eq(
                            'governorate_id',
                            govId
                        )
                    )
                    .first();


            return governorate.set({

                date:
                    current.get(
                        'date'
                    ),

                rainfall_mm:
                    current.get(
                        'rainfall_mm'
                    ),

                temperature_c:
                    current.get(
                        'temperature_c'
                    ),

                pet_mm:
                    current.get(
                        'pet_mm'
                    ),

                ndvi:
                    current.get(
                        'ndvi'
                    ),

                ndvi_anomaly:
                    current.get(
                        'ndvi_anomaly'
                    ),

                vci:
                    current.get(
                        'vci'
                    ),

                lst_c:
                    current.get(
                        'lst_c'
                    ),

                lst_anomaly:
                    current.get(
                        'lst_anomaly'
                    ),

                tci:
                    current.get(
                        'tci'
                    ),

                soil_moisture:
                    current.get(
                        'soil_moisture'
                    ),

                soil_moisture_anomaly:
                    current.get(
                        'soil_moisture_anomaly'
                    ),

                soil_moisture_anomaly_pct:
                    current.get(
                        'soil_moisture_anomaly_pct'
                    ),

                vhi:
                    current.get(
                        'vhi'
                    )

            });

        }
    );


// 30. EXPORT GOVERNORATE GEOJSON

Export.table.toDrive({

    collection:
        latestMap,

    description:
        'governorates_latest',

    folder:
        EXPORT_FOLDER,

    fileNamePrefix:
        'governorates_latest',

    fileFormat:
        'GeoJSON'

});


// 31. MAP DISPLAY

Map.centerObject(
    governorates,
    7
);


// GOVERNORATE BOUNDARIES

Map.addLayer(
    governorates,
    {},
    'Tunisia Governorates'
);


// NDVI

Map.addLayer(

    latestImage.select(
        'ndvi'
    ),

    {
        min: 0,
        max: 0.8,
        palette: [
            'brown',
            'yellow',
            'green'
        ]
    },

    'Latest NDVI'

);


// VHI

Map.addLayer(

    latestImage.select(
        'vhi'
    ),

    {
        min: 0,
        max: 100,
        palette: [
            'red',
            'orange',
            'yellow',
            'green'
        ]
    },

    'Latest VHI'

);

