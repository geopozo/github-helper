"""A CLI dashboard for github status."""

import re
import warnings
from pathlib import Path

import aiofiles
import jq  # type: ignore [import-not-found]
import logistro
import orjson

from . import _gh_service as srv
from ._gh_service import GHError, ScopesError, ScopesWarning

_logger = logistro.getLogger(__name__)
_SCRIPT_DIR = Path(__file__).resolve().parent


class GHApi:
    """Provides access to status functions ontop of gh program."""

    def __init__(self):
        """Initializize a new GHApi, takes no arguments."""
        self._current_user = ""

    # untested
    def _check_scopes(self, scopes_had, scopes_needed, scopes_wanted):
        missing_scopes_needed = [
            scope for scope in scopes_needed if scope not in scopes_had
        ]
        missing_scopes_wanted = [
            scope for scope in scopes_wanted if scope not in scopes_had
        ]
        if missing_scopes_wanted:
            warnings.warn(
                "Missing scope may lead to missing information, etc. "
                f"Other scopes wanted: {missing_scopes_wanted}. Had: {scopes_had}. "
                "Try gh `auth refresh --scopes SCOPE,...`",
                category=ScopesWarning,
                stacklevel=1,
            )
        if scopes_needed:
            raise ScopesError(
                "Missing essential scopes: "
                f"Other scopes needed: {missing_scopes_needed}. Had: {scopes_had}. "
                "Try gh `auth refresh --scopes SCOPE,...`",
            )

    async def check_auth(self, *, cli_args=None):
        """Return true if user is logged in."""
        retval, _, _ = await srv.gh_call(
            "gh",
            "auth",
            "status",
            direct=bool(cli_args),
        )
        return retval

    def _check_retval(self, retval, err, **kwargs):
        if retval != 0:
            try:
                raise GHError(f"{err!s}, add'l: {kwargs.items()!s}")  # noqa: TRY301
            except GHError as e:
                raise e.with_traceback(e.__traceback__.tb_next) from None

    def _get_template_path(self, *, file_name):
        # no es mejor crear otro constante
        # _TEMPLATE_PATH = _SCRIPT_DIR / "templates"
        # y cuando quiere usarlo, solo tienes que escribir:
        #
        # path = _TEMPLATE_PATH / file_name
        # en vez de esta función definida
        # y una llamada de _get_template_path
        return _SCRIPT_DIR / f"templates/{file_name}"

    async def _load_json_file(self, *, path): # y por qué necesitamos *?
        if not Path(path).is_file():
            raise GHError(f"{path} not exist")

        async with aiofiles.open(path) as f:
            file = await f.read()
        return orjson.loads(file)
    # tal vez mejor en un module de utilidades?
    # _load_json(self, path) está bien

    async def _get_target_ruleset(self, *, path):
        if Path(path).is_file():
            return await self._load_json_file(path=path)

        if Path(path).is_dir():
            raise GHError("File name required")

        template_path = self._get_template_path(file_name=path)
        return await self._load_json_file(path=template_path)
    # no me gusta, la cosa es, bueno, esta es una función interna, no se necesitan
    # tantos checkeos.
    # si vamos a aceptar un path del usuario, tenemos que crear una buena logica
    # 1. si nos pasara un archivo
    # 2. si no nos pasara nada (predeterminado?)
    # 3. si nos pasar un directorio (buscamos archivo especifico o grupo)?
    # pero si dado que esta me parece solo una función interna, una utilidad, no
    # entiendo por qué la necesitamos.
    #
    # debes mostrarme la CLI diseñada y que quieres presentar el usuario, porque sí,
    # me parece que habría banderas para cambiar que configuración/plantilla se cargan.

    # también, es también un "load", no un "get", creo, "load_target_ruleset"

    # el orden de las funciones es raro
    # no estoy seguro que necesitamos otra función para esto pero realmente
    # es necesario, el orden de los argumentos en la firma es raro, y porqué
    # es un argumento privado?
    # y este debe estar mas cerca donde se usa, no arriba de comparer
    # se usa _ en argumentos para indicar que no vas a usar el argumentos.

    # también, usamos el nombre
    # get_algo_por_algo cuando tenemos OTRAS maneras de conseguir la misma cosa
    # get_eso_por_algo_diferente
    # pero en este caso, siempre necesitamos id, sí o no?
    async def _get_ruleset(self, *, owner, repo, ruleset_id):
        """Return ruleset for a user by ruleset id."""
        endpoint = f"repos/{owner}/{repo}/rulesets/{ruleset_id}"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        return orjson.loads(out)

    async def _json_comparer(self, *, origin, target, excluded_keys):
        differences = []
        all_keys = set(origin.keys()).union(target.keys())

        for key in all_keys:
            if key in excluded_keys:
                continue

            origin_value = origin.get(key)
            target_value = target.get(key)

            if origin_value != target_value:
                differences.append(
                    {"name": key, "origin": origin_value, "target": target_value},
                )
        return differences if differences else {"is_equal": True}

    async def get_orgs(self):
        """Return orgs for a user."""
        orgs_jq = jq.compile("map({ name: (.login) })")
        endpoint = "/user/orgs"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        orgs = orgs_jq.input_value(orjson.loads(out)).first()

        _ = await self.get_user()

        role_jq = jq.compile(".role")
        for org in orgs:
            endpoint = f"orgs/{org['name']}/memberships/{self._current_user}"
            _logger.debug(f"Calling API: {endpoint}")
            retval, out, err = await srv.gh_api(endpoint)
            self._check_retval(retval, err, **org, endpoint=endpoint)
            org["role"] = role_jq.input_value(orjson.loads(out)).first()
        return orgs

    async def get_user(self):
        """Return username."""
        if self._current_user:
            return {"user": self._current_user}

        user_jq = jq.compile("{ (.login): .id }")
        endpoint = "/user"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        user_data = user_jq.input_text(out.decode()).first()
        user_name = next(iter(user_data))
        self._current_user = user_name
        return {"user": user_name}

    async def get_scopes(self):
        """Return array of scopes."""
        scopes_re = re.compile(rb"\n< X-Oauth-Scopes: (.*)\n")
        cli_command = ["gh", "api", "/user", "--verbose"]
        _logger.debug(f"Calling CLI command: {' '.join(cli_command)}")
        retval, out, err = await srv.gh_call(*cli_command)
        self._check_retval(retval, err)
        match = scopes_re.search(out)
        if not match:
            raise GHError(
                (
                    "get_scopes couldn't find scopes for some reason. "
                    "Output:\n"
                    f"{out.decode()}"
                ),
            )
        scopes = [scope.strip() for scope in match[1].decode().split(",")]
        return [{"scope_name": scope} for scope in scopes]

    async def get_repos(self):
        """Return repos for a user."""
        repos_jq = jq.compile(
            r"map({"
            r"name: .name,"
            r"visibility: .visibility,"
            r"archived: .archived,"
            r"owner: .owner.login"
            r"})"
            r" | sort_by(.name)"
            r" | sort_by(.archived)"
            r" | reverse"
            r" | sort_by(.visibility)"
            r" | reverse",
        )
        endpoint = "/user/repos"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        repos = repos_jq.input_value(orjson.loads(out)).first()
        return repos

    async def get_tags(self, *, repo):
        """Return tags for a repo."""
        _ = await self.get_user()
        tags_jq = jq.compile("map({name: .name})")
        endpoint = f"repos/{self._current_user}/{repo}/tags"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        tags = tags_jq.input_value(orjson.loads(out)).first()
        return tags

    async def get_releases(self, *, repo):
        """Return releases for a repo."""
        _ = await self.get_user()
        releases_jq = jq.compile(
            r"map({"
            r"name: .name, "
            r"tag: .tag_name, "
            r"published: (.draft | not)"
            r"})",
        )
        endpoint = f"repos/{self._current_user}/{repo}/releases"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        releases = releases_jq.input_value(orjson.loads(out)).first()
        return releases

    # una buena utilidad
    # _split_full_name,
    # para mis utilidades que tienen que ser motodos, las pongo
    # más ariba en la clase, antes de __init__
    def _split_full_name(self, *, full_name):
        parts = full_name.split("/")
        if len(parts) > 1:
            owner = parts[0]
            repo = parts[1]
        else:
            owner = self._current_user
        return owner, repo
    # otro implementación:
    def _split_full_name(self, full_name):
        if "/" in full_name:
            return full_name.split("/")
        else:
            return self._current_user, full_name

    # es necesario ser función separada?
    def _validate_config_keys(self, *, keys):
        VALID_KEYS = {"repo", "include", "exclude"} # noqa: N806 local constant.
        if keys - VALID_KEYS:
            raise TypeError(f"Only keys {VALID_KEYS} are allowed.")

    # abusas el *

    def _get_rulesets_files(self, *, configs, repo_name):
        rulesets_files = set()
        for cfg in configs: # config es algo pero no es plural?
            # y que es r?
            self._validate_config_keys(keys=cfg.keys())

            if "repo" not in cfg:
                continue # error entonces
                # o talvez usamos estrategia parecida para tener un
                # "VALID_KEYS" y "MANDATORY KEYS"
            if "include" in cfg:
                if not isinstance(cfg["include"], list):
                    raise TypeError("'include' must be a list")
                 # no haces glob correcto
                 # usas fnmatch porfa. un paquete.
                if cfg["repo"] == "*" or cfg["repo"] == repo_name:
                    rulesets_files = rulesets_files | set(cfg["include"])
            if "exclude" in cfg:
                if not isinstance(cfg["exclude"], list):
                    raise TypeError("'exclude' must be a list")
                if cfg["repo"] == repo_name: # te faltan un buen match
                    rulesets_files = rulesets_files - set(cfg["exclude"])
        return rulesets_files

    async def audit_rulesets_repo(self, *, repo):
        """
        Verify that repos have the proper branch/tag protections or find differences.

        Args:
            repo: the name of the repo to verify. Can be "owner/repo" or just
            "repo" and owner is assumed to be the current user.

        """
        default_file = "audit-config.json"
        rulesets_jq = jq.compile("map({(.name): .id}) | add")
        config_file = self._get_template_path(file_name=default_file)
        config_json = await self._load_json_file(path=config_file)
        _ = await self.get_user()
        owner, repo = self._get_repo_full_name(repo=repo)
        repo_name = f"{owner}/{repo}"
        files_names = self._get_rulesets_files(config=config_json, repo_name=repo_name)

        endpoint = f"repos/{owner}/{repo}/rulesets"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        rulesets = rulesets_jq.input_value(orjson.loads(out)).first()

        if not rulesets:
            return []

        excluded_keys = [
            "id",
            "source_type",
            "source",
            "node_id",
            "created_at",
            "updated_at",
            "_links",
        ]
        result = [
            {"parent": m, "status": "missing", "differences": []}
            for m in files_names
            if m not in rulesets
        ]

        for k, v in rulesets.items():
            json_file = f"{k}.json"
            if k not in files_names:
                result.append({"parent": k, "status": "additional", "differences": []})
                continue
            json_origin = await self._get_ruleset_by_id(_id=v, owner=owner, repo=repo)
            json_target = await self._get_target_ruleset(path=json_file)
            differences = await self._json_comparer(
                origin=json_origin,
                target=json_target,
                excluded_keys=excluded_keys,
            )
            result.append({"parent": k, "status": "found", "differences": differences})
        return result
