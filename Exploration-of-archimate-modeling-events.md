# ArchiMate Modeling Events — EventStoreML Inspiration

This document captures an exploration of what might happen to an ArchiMate model — seen through the lens of EventStoreML.  
It is merely an inspirational taxonomy of modeling events that could be represented as ESML event types.  
The idea: every modeling action is an event, and by recording these as append-only ESML streams, 
we can reconstruct or analyze the entire evolution of an enterprise architecture model.

---

## Layer 1 — Structural / CRUD Operations
Atomic mechanical actions that manipulate the ArchiMate model structure.
These correspond to what tools like Archi or BizzDesign actually record as model-edit operations.

```
archi.ModelCreated
archi.ModelRenamed
archi.ModelDocumentationSet
archi.ModelDocumentationCleared
archi.ModelPropertyAdded
archi.ModelPropertyRemoved
archi.ModelPropertyValueChanged
archi.FolderCreated
archi.FolderRenamed
archi.FolderMoved
archi.FolderDeleted
archi.ElementCreated
archi.ElementCloned
archi.ElementMovedToFolder
archi.ElementRenamed
archi.ElementTypeChanged
archi.ElementSpecializationSet
archi.ElementSpecializationCleared
archi.ElementDocumentationSet
archi.ElementDocumentationCleared
archi.ElementPropertyAdded
archi.ElementPropertyValueChanged
archi.ElementPropertyRemoved
archi.ElementDeleted
archi.RelationshipCreated
archi.RelationshipRenamed
archi.RelationshipTypeChanged
archi.RelationshipReconnectedSource
archi.RelationshipReconnectedTarget
archi.RelationshipDocumentationSet
archi.RelationshipDocumentationCleared
archi.RelationshipPropertyAdded
archi.RelationshipPropertyValueChanged
archi.RelationshipPropertyRemoved
archi.RelationshipDeleted
archi.ViewCreated
archi.ViewRenamed
archi.ViewDocumentationSet
archi.ViewDocumentationCleared
archi.ViewpointSet
archi.ViewpointCleared
archi.ViewDeleted
archi.ViewElementAdded
archi.ViewElementRemoved
archi.ViewRelationshipAdded
archi.ViewRelationshipRemoved
archi.PropertyDefinitionCreated
archi.PropertyDefinitionRenamed
archi.PropertyDefinitionDeleted
```

---

## Layer 2 — Semantic-Level Events
Modeling actions that change the meaning or conceptual content of the architecture.

```
archi.ConceptDeclared
archi.ConceptDeprecated
archi.ConceptMerged
archi.ConceptSplit
archi.ConceptReclassified
archi.ConceptRelated
archi.ConceptUnrelated
archi.ConceptAssignedToLayer
archi.ConceptRealizedBy
archi.ConceptSpecializedFrom
archi.ConceptCompositionAdded
archi.ConceptCompositionRemoved
archi.ConceptAggregationAdded
archi.ConceptAggregationRemoved
archi.ConceptServingAdded
archi.ConceptServingRemoved
archi.ConceptAccessAdded
archi.ConceptAccessRemoved
archi.ConceptTriggeringAdded
archi.ConceptTriggeringRemoved
archi.ConceptFlowAdded
archi.ConceptFlowRemoved
archi.ConceptUsedBy
archi.ConceptUsedByRemoved
archi.ConceptInfluenceAdded
archi.ConceptInfluenceRemoved
archi.ConceptAssignmentAdded
archi.ConceptAssignmentRemoved
archi.ConceptAssociationAdded
archi.ConceptAssociationRemoved
archi.ConceptRealizationAdded
archi.ConceptRealizationRemoved
archi.ConceptImplements
archi.ConceptImplementsRemoved
archi.CapabilityMaturitySet
archi.CapabilityMaturityChanged
archi.CapabilityMaturityCleared
archi.CapabilityPerformanceChanged
archi.CapabilityResourceLinked
archi.CapabilityResourceUnlinked
archi.BusinessProcessStepAdded
archi.BusinessProcessStepRemoved
archi.BusinessProcessFlowLinked
archi.BusinessProcessFlowUnlinked
archi.ApplicationServiceLinked
archi.ApplicationServiceUnlinked
archi.DataObjectLinked
archi.DataObjectUnlinked
archi.TechnologyNodeLinked
archi.TechnologyNodeUnlinked
archi.InterfaceExposed
archi.InterfaceHidden
archi.RequirementLinked
archi.RequirementSatisfied
archi.RequirementUnsatisfied
archi.ConstraintAdded
archi.ConstraintRemoved
archi.GoalLinked
archi.GoalAchieved
archi.GoalAbandoned
archi.OutcomeRealized
archi.OutcomeObsoleted
archi.AssessmentAdded
archi.AssessmentRemoved
archi.WorkPackagePlanned
archi.WorkPackageCompleted
archi.PlateauDeclared
archi.PlateauEnded
archi.GapIdentified
archi.GapClosed
```

---

## Layer 3 — View and Visualization-Level Events
Changes to model *views* that alter how concepts are represented or grouped semantically.

```
archi.ViewpointSelected
archi.ViewpointCustomized
archi.LayerVisibilityChanged
archi.ConnectionVisibilityChanged
archi.ViewGroupingAdded
archi.ViewGroupingRemoved
archi.ViewFilterApplied
archi.ViewFilterCleared
```

---

## Layer 4 — Cross-Model Integration Events
Interactions between multiple models or external data sources.

```
archi.ModelImported
archi.ModelElementLinkedExternal
archi.ModelElementUnlinkedExternal
archi.ModelMerged
archi.ModelSplit
archi.ModelCrossReferenceAdded
archi.ModelCrossReferenceRemoved
archi.ModelSubViewCreated
archi.ModelSubViewDeleted
```

---

## Layer 5 — Meta-Model Evolution
Extending or refining the ArchiMate meta-model itself within a model.

```
archi.MetaclassDefined
archi.MetaclassDeprecated
archi.MetaclassPropertyAdded
archi.MetaclassPropertyRemoved
archi.MetaclassSpecialized
archi.MetaclassRelationConstraintAdded
archi.MetaclassRelationConstraintRemoved
archi.LayerDefined
archi.LayerExtended
archi.LayerDeprecated
```

---

## Layer 6 — Validation and Consistency Events
Model-internal validation and rule-checking events.

```
archi.ValidationRuleViolated
archi.ValidationRuleSatisfied
archi.ValidationRuleAdded
archi.ValidationRuleRemoved
archi.IntegrityCheckPassed
archi.IntegrityCheckFailed
```

---

## Layer 7 — Collaboration Modeling Events
Multi-user collaboration and review interactions that still belong to model context.

```
archi.LockAcquired
archi.LockReleased
archi.CommentAdded
archi.CommentResolved
archi.AnnotationAdded
archi.AnnotationRemoved
archi.ReviewStarted
archi.ReviewCompleted
archi.ChangeRequestLinked
archi.ChangeRequestClosed
archi.MergeConflictResolved
```

---

*Reminder: This list is just for inspiration. A proper approach would likely lead to a different set of events.*
