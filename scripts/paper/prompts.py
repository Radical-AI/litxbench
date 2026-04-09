example = """
[
  Experiment(
    raw_materials={
      "elements": RawMaterial(
        kind=RawMaterialKind.Ingot,
        description="...",
        source="...",
      )
    },
    synthesis_groups={
      "creation": [
        ProcessEvent(kind=ProcessKind.ArcMelting, description="Remelted 5 times to promote homogeneity, flipped pellet between each remelt", source="..."),
        ProcessEvent(kind=ProcessKind.AsCast, description="...", source="..."),
        ProcessEvent(kind=ProcessKind.Homogenization, temperature=Quantity(value=1200, unit=Celsius), duration=Quantity(value=24, unit=ureg.hour), source="..."),
        ProcessEvent(kind=ProcessKind.WaterQuenching, source="..."),
      ],
      "annealing[Temp]": [
        ProcessEvent(
          kind=ProcessKind.Annealing,
          temperature=Quantity(value="[Temp]", unit=Celsius),
          source="...",
        ),
      ],
    },
    descriptions=[
      AlloyDescriptionGroup(
        kinds=[AlloyMeasurementKind.vickers_hardness],
        method=MeasurementMethod.VickersHardnessTest,
        desc="The microhardness (HV) of the alloys was measured with a Vickers hardness tester under a load of 500 gf",
      ),
      AlloyDescriptionGroup(
        kinds=[ProcessKind.Grinding],
        desc="performed on a grinding wheel",
      ),
    ],
    output_materials=[
      Material(
        process="elements->creation",
        name="materialA",
        measurements=[
          CompositionMeasurement("MgFeNi"),
          Measurement(
            kind=AlloyMeasurementKind.vickers_hardness,
            value=321.0,
            unit=HV,
            uncertainty=7.0,
            source="...",
          ),
          # When a value is explicitly a mean/average:
          Measurement(
            kind=AlloyMeasurementKind.yield_strength_tension,
            value=450.0,
            unit=MegaPascal,
            measurement_statistic=MeasurementStatistic.mean,
            source="...",
          ),
          # When a value is reported as a range (e.g. "5–50 μm"):
          *Measurement.group_measurements(
            kind=PhaseMeasurementKind.grain_size,
            unit=Micrometer,
            values=[
              CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=5),
              CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=50),
            ],
          ),
          # XRD-determined lattice parameter and crystal structure:
          GlobalLatticeParam(
            lattice=LatticeMeasurement(Lattice.cubic(3.208)),
            struct=CrysStruct.BCC,
            source="...",
          ),
          # Microstructural feature (e.g. dendrite with EDS composition):
          Configuration(
            name="dendrite",
            tags={ConfigTag.Dendrite},
            measurements=[
              CompMeasurement(
                {"Mo": 27.6, "Nb": 25.0, "Ta": 31.5, "V": 15.9},
                method=MeasurementMethod.EDS,
                source="...",
              ),
            ],
          ),
          # Nested configuration (precipitate within a phase):
          Configuration(
            name="FCC matrix",
            struct=CrysStruct.FCC,
            tags={ConfigTag.Matrix},
            measurements=[
              Measurement(
                kind=PhaseMeasurementKind.grain_size,
                value="~0.71",
                unit=Micrometer,
              ),
            ],
          ),
          Configuration(
            name="B2 precipitates",
            struct=CrysStruct.B2,
            tags={ConfigTag.Precipitate, ConfigTag.Intragranular},
            within="FCC matrix",
            measurements=[
              *Measurement.group_measurements(
                kind=PhaseMeasurementKind.grain_size,
                unit=Nanometer,
                values=[
                  CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=50),
                  CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=180),
                ],
              ),
            ],
          ),
        ],
      ),
      Material(
        process="materialA->annealing[Temp=10]",
        name="materialB",
        measurements=[
          CompositionMeasurement("MgFeNi"),
          Measurement(
            kind=AlloyMeasurementKind.vickers_hardness,
            value=350.0,
            unit=HV,
            uncertainty=7.0,
            source="...",
          ),
        ],
      ),
    ],
  ),
]
"""
