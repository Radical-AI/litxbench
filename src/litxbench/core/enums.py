"""Enum definitions for the experiment extraction framework."""

from enum import Enum


class ValueQualifier(str, Enum):
    """Indicates the relationship between a reported value and its true value (e.g., exact, approximate, upper/lower bound)."""

    EXACT = "exact"
    APPROXIMATE = "approximate"
    ABOVE = "above"
    BELOW = "below"
    ABOVE_OR_EQUAL = "above_or_equal"
    BELOW_OR_EQUAL = "below_or_equal"
    MUCH_ABOVE = "much_above"
    MUCH_BELOW = "much_below"


class MeasurementMethod(str, Enum):
    """Characterization instruments and techniques used to measure material properties or composition."""

    XRD = "xray_diffractometer"
    DSC = "differential_scanning_calorimeter"
    TensileTest = "tensile_test"
    CompressionTest = "compression_test"
    VickersHardnessTest = "vickers_hardness_test"
    NanoindentTest = "nanoindent_test"
    ArchimedesMethod = "archimedes_method"
    OpticalMicroscope = "optical_microscope"
    SEM = "scanning_electron_microscope"
    TEM = "transmission_electron_microscope"
    STEM = "scanning_transmission_electron_microscope"
    EBSD = "electron_backscatter_diffraction"
    UniversalTestingMachine = (
        "universal_testing_machine"  # measures tons of mechanical properties (tensile, compression, bending, etc.)
    )
    ResonanceUltrasoundSpectroscopy = "resonance_ultrasound_spectroscopy"
    FractureToughnessTest = "fracture_toughness_test"

    # Composition measurement methods
    Balance = "balance"
    EDS = "energy_dispersive_xray_spectroscopy"
    TEM_EDS = "tem_energy_dispersive_xray_spectroscopy"
    WDS = "wavelength_dispersive_xray_spectroscopy"
    EPMA = "electron_probe_microanalysis"  # uses WDS - but it's better to have a separate enum value for this
    LIBS = "laser_induced_breakdown_spectroscopy"
    ED_XRF = "energy_dispersive_xray_fluorescence"
    WD_XRF = "wavelength_dispersive_xray_fluorescence"
    Spark_OES = "spark_optical_emission_spectroscopy"
    ICP_OES = "inductively_coupled_plasma_optical_emission_spectroscopy"
    ICP_MS = "inductively_coupled_plasma_mass_spectroscopy"
    Unspecified = "unspecified"


# This is stuff you can never see from an SEM image.
class CrysStruct(str, Enum):
    """Crystal structure types including basic lattices, ordered intermetallics, and compound structures."""

    # Pure Metals / Basic
    FCC = "FCC"
    BCC = "BCC"
    HCP = "HCP"
    DHCP = "DHCP"
    Diamond = "Diamond"

    # Ordered Intermetallics
    L12 = "L12"  # Ordered FCC (e.g., Ni3Al)
    L10 = "L10"  # Tetragonal FCC (e.g., FePt)
    B2 = "B2"  # Ordered BCC (e.g., NiAl)
    D019 = "D019"  # Ordered HCP (e.g., Ti3Al)
    D03 = "D03"  # Ordered BCC variant (e.g., Fe3Al)
    Heusler = "Heusler"

    # Common Compounds / Laves
    Rocksalt = "B1"  # NaCl-type (e.g., TiC, TiN)
    Zincblende = "B3"  # e.g., GaAs
    C14 = "C14"  # Laves phase (Hexagonal)
    C15 = "C15"  # Laves phase (Cubic)
    Perovskite = "E21"

    # Disorder / Meta
    Amorphous = "Amorphous"
    Unknown = "Unknown"


class ConfigTag(str, Enum):
    """Microstructural features and morphological tags describing a phase's configuration within the material."""

    # Growth & Solidification
    Dendrite = "dendrite"
    Interdendritic = "interdendritic"
    Equiaxed = "equiaxed"
    Columnar = "columnar"

    Eutectic = "eutectic"
    Coring = "coring"

    # Transformation Products
    Lath = "lath"
    Martensite = "martensite"  # there's precipitates within grains
    Acicular = "acicular"
    Lamellar = "lamellar"  # lamellar -> looks like waves
    Widmanstatten = "widmanstatten"

    # Locations & Interfaces
    Matrix = "matrix"
    Precipitate = "precipitate"
    Intragranular = "intragranular"  # Inside grains
    Intergranular = "intergranular"  # At boundaries

    # Chemistry/Defects
    Segregation = "segregation"
    Twin = "twin"
    Subgrain = "subgrain"

    # Meta
    Structure = "structure"
    Unknown = "unknown"


class ProcessKind(str, Enum):
    """Processing steps in the fabrication pipeline, from synthesis and melting through thermal treatment to finishing."""

    # --- Synthesis & Melting ---
    Mixing = "Mixing"
    MechanicalAlloying = "Mechanical Alloying"
    PlanetaryMilling = "Planetary Milling"
    GasAtomization = "Gas Atomization"

    ArcMelting = "Arc Melting"
    InductionMelting = "Induction Melting"

    CastingUnspecified = "Casting Unspecified"
    AsCast = "As Cast"
    GravityCasting = "Gravity Casting"
    DropCasting = "Drop Casting"
    SuctionCasting = "Suction Casting"
    DirectionalSolidification = "Directional Solidification"

    # --- Sintering ---
    # cooling is implied after sintering so we don't have a dedicated Cooling kind
    SparkPlasmaSintering = "Spark Plasma Sintering"
    HotPressingSintering = "Hot Pressing Sintering"

    # --- Thermal Treatment ---
    VacuumFurnace = "Vacuum Furnace"
    Homogenization = "Homogenization"
    Annealing = "Annealing"
    NonIsothermalAnnealing = "Non-Isothermal Annealing"
    IsothermalHolding = "Isothermal Holding"
    WaterQuenching = "Water Quenching"
    SolutionHeatTreatment = "Solution Heat Treatment"

    # --- Mechanical Working ---
    HotExtrusion = "Hot Extrusion"
    HotRolling = "Hot Rolling"
    ColdRolling = "Cold Rolling"
    CrossRolling = "Cross Rolling"
    ColdForging = "Cold Forging"
    Press = "Press"
    FrictionStirProcessing = "Friction Stir Processing"

    # --- Finishing & Preparation ---
    ElectricalDischargeMachining = "Electro-Discharge Machining"
    Cut = "Cut"
    Grinding = "Grinding"
    Polishing = "Polishing"
    Etching = "Etching"
    AquaRegia = "AquaRegia"
    SandBlasting = "Sand Blasting"
    Degreased = "Degreased"
    UltrasonicBath = "Ultrasonic Bath"
    AirDrying = "Air Drying"


MELTING_KINDS = {ProcessKind.ArcMelting, ProcessKind.InductionMelting}
CASTING_KINDS = {
    ProcessKind.CastingUnspecified,
    ProcessKind.AsCast,
    ProcessKind.GravityCasting,
    ProcessKind.DropCasting,
    ProcessKind.SuctionCasting,
    ProcessKind.DirectionalSolidification,
}


class RawMaterialKind(str, Enum):
    """Physical form of the starting material used in the fabrication process."""

    Ingot = "ingot"
    Powder = "powder"
    Plate = "plate"
    Unspecified = "unspecified"
    Other = "other"
