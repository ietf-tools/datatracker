CHART_TYPE_COLUMN_OPTIONS = {
    "chart": {
        "type": 'column',
    },
    "credits": {
        "enabled": False,
    },
    "exporting": {
        "fallbackToExportServer": False,
    },
    "rangeSelector" : {
        "selected": 5,
        "allButtonsEnabled": True,
    },
    "series" : [{
        "name" : "Items",
        "type" : "column",
        "data" : [],
        "dataGrouping": {
            "units": [[
                'week',                                 # unit name
                [1,],                                   # allowed multiples
            ], [
                'month',
                [1, 4,],
            ]]
        },
        "turboThreshold": 1, # Only check format of first data point. All others are the same
        "pointIntervalUnit": 'day',
        "pointPadding": 0.05,
    }],
    "title" : {
        "text" : "Items over time"
    },
    "xAxis": {
        "type": "datetime",
        # This makes the axis use the given coordinates, rather than
        # squashing them to equidistant columns
        "ordinal": False,
    },
}

CHART_TYPE_ACTIVITY_OPTIONS = {
    "chart": {
        "type": 'column',
    },
    "credits": {
        "enabled": False,
    },
    "exporting": {
        "fallbackToExportServer": False,
    },
    "navigation": {
        "buttonOptions": {
            "enabled": False,
        }
    },
    "navigator": {
        "enabled": False,
    },
    "rangeSelector" : {
        "enabled": False,
    },
    "scrollbar": {
        "enabled": False,
    },
    "series" : [{
        "name" : None,
        "animation": False,
        "type" : "column",
        "data" : [],
        "dataGrouping": {
            "units": [[
                'year',                                 # unit name
                [1,],                                   # allowed multiples
            ]]
        },
        "turboThreshold": 1, # Only check format of first data point. All others are the same
        "pointIntervalUnit": 'day',
        "pointPadding": -0.2,
    }],
    "title" : {
        "text" : None,
    },
    "xAxis": {
        "type": "datetime",
        # This makes the axis use the given coordinates, rather than
        # squashing them to equidistant columns
        "ordinal": False,
    },
    "yAxis": {
        "labels": {
            "enabled": False,
        }
    },
}

