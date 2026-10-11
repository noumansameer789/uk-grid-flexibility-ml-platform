# Data attribution

Carbon data is from the **NESO Carbon Intensity API**, developed by the National Energy System Operator and collaborators. Source: https://carbonintensity.org.uk/ and https://api.carbonintensity.org.uk/. API definitions: https://carbon-intensity.github.io/api-definitions/.

The API data is made available under **Creative Commons Attribution 4.0 International**: https://creativecommons.org/licenses/by/4.0/. The committed carbon reference and transformed model features retain this attribution. Changes include UTC normalisation, half-open interval filtering, numeric conversion, lag construction and statistical modelling. NESO does not endorse this project.

Weather data is from **Open-Meteo**, https://open-meteo.com/, under its data attribution terms (CC BY 4.0). It aggregates meteorological models/reanalysis from providers including ECMWF and national weather services. The pipeline records the endpoint and coordinates. Source data is normalised and averaged across London, Manchester and Edinburgh for contextual display; it is not used by the current carbon model. Free API usage is subject to Open-Meteo's current service terms and limits; commercial use may require a subscription.

The synthetic arrays in tests are generated solely for software verification and are not presented as observed grid data. Code is MIT-licensed separately from the source datasets.
