"""
 Created on June 23, 2022

@author: joseph-hellerstein

Analysis abstraction for an SBML model.
The state of a model is specified by the current simulation time and the values
of the parameters. Changes to reactions are not preserved by copy, serialize, deserialize.

Usage example:
    # Construction
    model = Model(path_to_SBML_model)
    # Model manipulation
    parameter_value = model.get(parameter_name)
    model.set({"k1": 1, "k2": 2})
    ts = model.simulate(0, 10, 100)
    # Save model to a file
    with open(path_to_file, "wb") as fd:
        rpickle.dump(model, fd)
    # Load model from a file
    with open(path_to_file, "rb") as fd:
        recovered_model = rpickle.load(fd)
"""

"""
TO DO:
1. self.kinetics_dct: reaction name, kinetics law
2. Test subclassing
"""

import analyzeSBML.constants as cn
from analyzeSBML import rpickle
import analyzeSBML as anl
from analyzeSBML import util

import copy
import lmfit
import numpy as np
import tellurium as te
import typing

# Attributes
MODEL_REFERENCE = "model_reference"
ANTIMONY = "antimony"
PARAMETER_DCT = "parameter_dct"

DESERIALIZATION_DCT = "deserialization_dct"
CURRENT_TIME = "current_time"
IS_DEBUG = True


class Model(rpickle.RPickler):

    # Attributes saved on serialization
    # Append other attributes in subclass
    SERIALIZATION_ATRS = [MODEL_REFERENCE, ANTIMONY]
    # Attributes checked for equality betweeen objects
    ISEQUAL_ATRS = [ANTIMONY, "species_names", "parameter_names", "reaction_names",
          "kinetic_dct",  MODEL_REFERENCE]

    def __init__(self, model_reference=None):
        """
        Abstraction for analysis of an SBML model.

        Parameters
        ----------
        model_reference: reference to an SBML model
            ExtendedRoadrunner
            File path
            URL
            String
          Model reference is None to construct a default object
          for serialization
        """
        if model_reference is not None:
            self.model_reference = model_reference  # MODEL_REFERENCE
            self.roadrunner = anl.makeRoadrunner(self.model_reference)  # MODEL_REFERENCE
            self.deserialization_dct = None
            self._initialize()
        else:
            # Constructing deserialized object
            pass

    def _initialize(self):
        self.antimony = self.roadrunner.getAntimony()
        self.species_names = self.roadrunner.getFloatingSpeciesIds()
        self.parameter_names = self.roadrunner.getGlobalParameterIds()
        self.reaction_names = self.roadrunner.getReactionIds()
        self.kinetic_dct = {n: self.roadrunner.getKineticLaw(n)
              for n in self.reaction_names}

    def isEqual(self, other):
        """
        Checks if this model is the same as another.

        Parameters
        ----------
        other: Model
        
        Returns
        -------
        bool
        """
        for attr in self.ISEQUAL_ATRS:
            if not util.isEqual(self.__getattribute__(attr),
                  other.__getattribute__(attr)):
                if IS_DEBUG:
                    import pdb; pdb.set_trace()
                return False
        #
        if self.getTime() != other.getTime():
            return False
        #
        return True
                
    def rpSerialize(self, dct):
        """
        Edit the dictionary being saved
        Parameters
        ----------
        dct: dict
        """
        # Delete the roadrunner object since it cannot be serialized
        old_dct = dict(dct)
        for key, value in old_dct.items():
            if not key in self.SERIALIZATION_ATRS:
                del dct[key]
        # Record deserialization information
        parameter_dct = self.get(self.parameter_names)
        deserialization_dct = {CURRENT_TIME: self.getTime(),
              PARAMETER_DCT: parameter_dct}
        dct[DESERIALIZATION_DCT] = deserialization_dct

    @classmethod
    def rpConstruct(cls):
        """
        Provides a default construction of an object.

        Returns
        -------
        Instance of cls
        """
        return cls(None)

    def rpDeserialize(self):
        """
        Provides a hook to modify instance variables after they have
        been initialized by RPickle.
        """
        deserialization_dct = dict(self.deserialization_dct)  # DESERIALIZAITON_DCT
        self.roadrunner = te.loada(self.antimony)
        self._initialize()
        self.set(deserialization_dct[PARAMETER_DCT])
        self.setTime(deserialization_dct[CURRENT_TIME])

    def set(self, name_dct):
        """
        Sets the values of names and values.

        Parameters
        ----------
        name_dct: dict
            key: str
            value: value
        """
        util.setRoadrunnerValue(self.roadrunner, name_dct)

    def get(self, names=None):
        """
        Provides the roadrunner values for a name. If no name,
        then all values are given.

        Parameters
        ----------
        name: str/list-str

        Returns
        -------
        object/dict
        """
        if names is None:
            names = self.roadrunner.keys()
        return util.getRoadrunnerValue(self.roadrunner, names)

    def getTime(self):
        """
        Gets current simulation time.

        Returns
        -------
        float
        """
        return self.roadrunner.model.getTime()

    def setTime(self, time):
        """
        
        Parameters
        ----------
        
        Returns
        -------
        """
        self.roadrunner.reset()
        if time > 0.01:
            _ = self.roadrunner.simulate(0.0, time)

    def copy(self):
        """
        Creates a copy of the model. Preserves the model parameters
        and curent time.
        
        Returns
        -------
        Model
        """
        serializer = rpickle.Serializer(self)
        serializer.serialize()
        return serializer.deserialize()
 
    def simulate(self, *pargs, **kwargs):
        """
        Runs a simulation. Defaults to parameter values in the simulation.
        Returns a NamedTimeseries.

        Return
        ------
        NamedTimeseries (or None if fail to converge)
        """
        data = self.roadrunner.simulate(*pargs)
        columns = [c[1:-1] if c[0] =="[" else c for c in data.colnames]
        return anl.Timeseries(data, columns=columns)