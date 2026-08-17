try:
	from .neuropatch_types import PatchError
except ImportError:
	from neuropatch_types import PatchError


OPERATION_CONTRACTS = {
	"create_file": {
		"required": {"file", "content"},
		"nested_allowed": False,
	},
	"modify_file": {
		"required": {"file", "operations"},
		"nested_allowed": True,
	},
	"replace": {
		"required": {"file", "old", "new"},
		"nested_allowed": True,
	},
	"delete_file": {
		"required": {"file"},
		"nested_allowed": False,
	},
}


SUPPORTED_OPERATIONS = set(OPERATION_CONTRACTS)


SUPPORTED_NESTED_OPERATIONS = {
	"modify_file": {
		operation
		for operation, contract in OPERATION_CONTRACTS.items()
		if contract["nested_allowed"]
	},
}


def validate_patch(patch):
	for key in ["patch_id", "goal", "operations"]:
		if key not in patch:
			raise PatchError(f"Missing {key}")

	if not isinstance(patch["operations"], list):
		raise PatchError("Invalid operations: expected list")

	if "validation" in patch and not isinstance(patch["validation"], dict):
		raise PatchError("Invalid validation: expected object")

	if "git" in patch and not isinstance(patch["git"], dict):
		raise PatchError("Invalid git: expected object")


def validate_operation_schema(operation):
	operation_type = operation.get("type")
	contract = OPERATION_CONTRACTS.get(operation_type, {})

	required = contract.get("required", set())
	missing = sorted(
		field
		for field in required
		if field not in operation
	)

	if missing:
		raise PatchError(
			f"Invalid operation: type={operation_type} "
			f"missing={','.join(missing)}"
		)


def validate_operations(patch):
	for operation in patch["operations"]:
		if operation["type"] not in SUPPORTED_OPERATIONS:
			raise PatchError(
				f"Unsupported operation: {operation['type']}. "
				f"Supported operations: "
				f"{', '.join(sorted(SUPPORTED_OPERATIONS))}"
			)

		validate_operation_schema(operation)

		if operation["type"] == "modify_file":
			for nested_operation in operation.get("operations", []):
				allowed = SUPPORTED_NESTED_OPERATIONS["modify_file"]

				if nested_operation["type"] not in allowed:
					raise PatchError(
						f"Unsupported nested operation: "
						f"{nested_operation['type']}. "
						f"Allowed: {', '.join(sorted(allowed))}"
					)

				validate_operation_schema({
					**nested_operation,
					"file": operation["file"],
				})
