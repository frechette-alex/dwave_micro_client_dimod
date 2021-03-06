"""
EmbeddingComposite
==================
"""
import itertools

import dimod
import dwave_embedding_utilities as embutil
import minorminer


class EmbeddingComposite(dimod.Sampler, dimod.Composite):
    """Composite to map unstructured problems to a structured sampler.

    Args:
        sampler (:class:`dimod.TemplateSampler`):
            A structured dimod sampler to be wrapped.

    """
    def __init__(self, sampler):
        # The composite __init__ adds the sampler into self.children
        dimod.Sampler.__init__(self)
        dimod.Composite.__init__(self, sampler)

    def sample_ising(self, h, J, **kwargs):
        """Sample from the provided unstructured Ising model.

        Args:
            h (list/dict): Linear terms of the model.
            J (dict of (int, int):float): Quadratic terms of the model.
            **kwargs: Parameters for the sampling method, specified per solver.

        Returns:
            :class:`dimod.SpinResponse`

        """
        # solve the problem on the child system
        child = self.child

        # apply the embedding to the given problem to map it to the child sampler
        __, target_edgelist, target_adjacency = child.structure

        # get the embedding
        embedding = minorminer.find_embedding(J, target_edgelist)

        if J and not embedding:
            raise ValueError("no embedding found")

        # this should change in later versions
        if isinstance(embedding, list):
            embedding = dict(enumerate(embedding))

        h_emb, J_emb, J_chain = embutil.embed_ising(h, J, embedding, target_adjacency)
        J_emb.update(J_chain)

        response = child.sample_ising(h_emb, J_emb, **kwargs)

        # unembed the problem and save to a new response object
        samples = embutil.unembed_samples(response, embedding,
                                          chain_break_method=embutil.minimize_energy,
                                          linear=h, quadratic=J)  # needed by minimize_energy
        source_response = dimod.Response(dimod.SPIN)

        for sample, (__, data) in zip(samples, response.df_data.iterrows()):

            data['energy'] = dimod.ising_energy(sample, h, J)

            source_response.add_sample(sample, **data.to_dict())

        return source_response
