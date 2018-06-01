from rllab.envs.mujoco.ant_env import AntEnv
from rllab.core.serializable import Serializable
from sandbox.jonas.envs.mujoco.base_env_rand_param import BaseEnvRandParams
from sandbox.jonas.envs.helpers import get_all_function_arguments

from rllab.misc.overrides import overrides
from rllab.envs.base import Step
from rllab.misc import logger

import numpy as np



class AntEnvRandParams(BaseEnvRandParams, AntEnv, Serializable):

    FILE = 'ant.xml'
    ORI_IND = 3

    def __init__(self, *args, log_scale_limit=2.0, fix_params=False, rand_params=BaseEnvRandParams.RAND_PARAMS, random_seed=None, max_path_length=None, **kwargs):
        """
        Half-Cheetah environment with randomized mujoco parameters
        :param log_scale_limit: lower / upper limit for uniform sampling in logspace of base 2
        :param random_seed: random seed for sampling the mujoco model params
        :param fix_params: boolean indicating whether the mujoco parameters shall be fixed
        :param rand_params: mujoco model parameters to sample
        """

        args_all, kwargs_all = get_all_function_arguments(self.__init__, locals())
        BaseEnvRandParams.__init__(*args_all, **kwargs_all)
        AntEnv.__init__(self, *args, **kwargs)
        Serializable.__init__(*args_all, **kwargs_all)

    @overrides
    def step(self, action):
        self.forward_dynamics(action)
        comvel = self.get_body_comvel("torso")
        forward_reward = comvel[0]
        lb, ub = self.action_bounds
        scaling = (ub - lb) * 0.5
        ctrl_cost = 0.5 * 1e-2 * np.sum(np.square(action / scaling))
        contact_cost = 0.5 * 1e-3 * np.sum(
            np.square(np.clip(self.model.data.cfrc_ext, -1, 1))),
        survive_reward = 0.05
        reward = forward_reward - ctrl_cost - contact_cost + survive_reward
        state = self._state
        notdone = np.isfinite(state).all() and state[2] >= 0.2 and state[2] <= 1.0
        self.n_steps += 1
        done = not notdone or self.n_steps >= self.max_path_length
        ob = self.get_current_obs()

        # clip reward in case mujoco sim goes crazy
        reward = np.minimum(np.maximum(-1000.0, reward), 1000.0)

        return Step(ob, float(reward), done, reward_run=forward_reward, reward_ctrl=-ctrl_cost)

    def reward(self, obs, action, obs_next):
        lb, ub = self.action_bounds
        scaling = (ub - lb) * 0.5
        if obs.ndim == 2 and action.ndim == 2:
            assert obs.shape == obs_next.shape and action.shape[0] == obs.shape[0]
            forward_vel = (obs_next[:, -3] - obs[:, -3])/ 0.02
            ctrl_cost = 0.5 * 1e-2 * np.sum(np.square(action / scaling), axis=1)
            survive_reward = 0.05
            return forward_vel - ctrl_cost + survive_reward
        else:
            return self.reward(np.array([obs]), np.array([action]), np.array([obs_next]))[0]

    def done(self, obs):
        if obs.ndim == 2:
            notdone = np.all(np.isfinite(obs), axis=1) * (obs[:, 2] >= 0.2) * (obs[:, 2] <= 1.0)
            return np.logical_not(notdone)
        else:
            notdone = np.isfinite(obs).all()  and obs[2] >= 0.2 and obs[2] <= 1.0
            return not notdone




    @overrides
    def log_diagnostics(self, paths, prefix=''):
        progs = [
            path["observations"][-1][-3] - path["observations"][0][-3]
            for path in paths
        ]
        logger.record_tabular(prefix+'AverageForwardProgress', np.mean(progs))
        logger.record_tabular(prefix+'MaxForwardProgress', np.max(progs))
        logger.record_tabular(prefix+'MinForwardProgress', np.min(progs))
        logger.record_tabular(prefix+'StdForwardProgress', np.std(progs))

if __name__ == "__main__":
    env = AntEnvRandParams()
    env.reset()
    print(env.model.body_mass)
    for _ in range(1000):
        env.render()
        env.step(env.action_space.sample())  # take a random action